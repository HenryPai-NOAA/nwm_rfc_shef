#!/awips2/python/bin/python

# poc:          henry pai
# last edit:    feb 2025 
# last edit:    hp, feb 2025
# edit notes:   usbr scraper rewrite

# 
# https://nomads.ncep.noaa.gov/pub/data/nccf/com/nwm/post-processed/RFC/NW/channel_rt/



import pdb, os, json, argparse, pathlib, urllib, netCDF4, requests, yaml, logging, sys, time
import xarray as xr
import pandas as pd
import numpy as np

os.umask(0o002)

# === global var (not path related)
# NWRFC settings
out_fmt = 'csv'

# ==== directories & filenames (site specific)
if os.name == 'nt':
    work_dir = pathlib.Path(__file__).resolve().parents[1] # IDE independent, sets one dir above 
    meta_dir = os.path.join(work_dir, "etc")
    out_dir = os.path.join(work_dir, "data")
    log_dir = os.path.join(work_dir, "logs")
else:
    work_dir = pathlib.Path("/data/ldad/snotel/")
    meta_dir = work_dir
    out_dir = pathlib.Path("/data/Incoming/")
    log_dir = pathlib.Path("/data/ldad/logs/")

config_fn = 'config.yaml'
state_fn = 'nwm_status.yaml'
mapping_fn = 'lid_nwm_mapping.yaml'
log_fn = 'nwm_download.log'

# ===== url info
#nwm_base_url = 'https://nomads.ncep.noaa.gov/pub/data/nccf/com/nwm/post-processed/RFC/NW/channel_rt/'
nwm_pre = 'nwm.t'
nwm_post = '.channel_rt.nc'



# ===== initial set up for requests and logging
logging.basicConfig(format='%(asctime)s %(levelname)-4s %(message)s',
                    handlers=[logging.FileHandler(os.path.join(log_dir, log_fn), mode='w'),
                              logging.StreamHandler()],
                    #filename=os.path.join(log_dir, log_fn),
                    #filemode='w',
                    #level=logging.DEBUG,
                    level=logging.INFO,
                    datefmt='%Y-%m-%d %H:%M:%S')

# ===== functions
def parse_args():
    """
    Sets default arguments, defaul model is medium (medium_range_blend)
    """
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '--mod',
        default='medium',
        help="model type (short, medium)"
        )

    return parser.parse_args()

def load_config_states(file_type):
    '''
    loads and returns yaml config/states files
    '''
    if file_type == 'config':
        fn = config_fn
    elif file_type == 'state':
        fn = state_fn
    elif file_type == 'mapping':
        fn = mapping_fn
    
    logging.info('loading attempt for ' + file_type + ' file ' + fn)
    
    with open(os.path.join(meta_dir, fn)) as stream:
        try:
            yaml_stream = yaml.safe_load(stream)
        except IOError:
            if file_type == 'config':
                logging.info("No config file, 'cp doc/NwmToShef.config.example etc/NwmToShef.config' and edit as required.")
                sys.exit()
            else:
                logging.info('NWM ' + file_type  + ' file does not exist will create a file' + fn)

    return(yaml_stream)

def map_ids(config, request_header):

    if os.path.exists(os.path.join(meta_dir, mapping_fn)):
        nwm_map = load_config_states('mapping')
        logging.info('Checking mapping file')
    else:
        nwm_map = {}
        nwm_map["nwslid2nwm"] = {}

    for site in config['sites']:        
        if site.upper() not in nwm_map["nwslid2nwm"]:
            nwps_gage_url = config["NWPSapi"] + 'gauges/' + site
            try:
                response = requests.get(nwps_gage_url, headers=request_header)
            except IOError:
                logging.info("Failed to get metadata for " + site.upper() + " at: "+ nwps_gage_url)
                continue
            
            nwm_reach = response.json()["reachId"]
            if nwm_reach == '':
                logging.info("Valid lid for " + site + ", but empty NWM reachId.  Will not map.")
            else:
                logging.info("New NWM reachId for " + site + " : "+ nwm_reach)
                nwm_reach = int(nwm_reach)
                nwm_map["nwslid2nwm"][site.upper()] = nwm_reach
            
        else:
            nwm_reach = nwm_map["nwslid2nwm"][site.upper()]    
            print("Cached NWM reachId " + site + " : " + str(nwm_reach))
        
    # sorting
    nwm_map['nwslid2nwm'] = dict(sorted(nwm_map['nwslid2nwm'].items()))

    with open(os.path.join(meta_dir, mapping_fn), 'w+') as yaml_file:
        yaml_file.write(yaml.dump(nwm_map, default_flow_style=False))

    map_df = pd.json_normalize(nwm_map['nwslid2nwm']).T.reset_index().set_axis(['lid','station_id'], axis=1)

    return map_df

def get_url_response(model_time, mod_type, request_header, config_vals):
    """
    generates url and does some url checking
    returns response
    """
    model_dt_str = model_time.strftime('%Y-%m-%d %HZ')
    url_dt_str = model_time.strftime('%Y%m%d%Hz')

    rfc_str = config_vals['rfc_id'].lower() + 'rfc'
    nwm_var_mod_type = [key for key, value in config_vals['nwm_var_meta'].items() if mod_type in key][0]

    full_url = (config_vals['nomads_rfc_url'] + config_vals['rfc_id'] + '/' + config_vals['nwm_type'] + '/' +           # path
                nwm_pre + url_dt_str + '.' + nwm_var_mod_type + '.' + config_vals['nwm_type'] + '.' + rfc_str + '.nc')  # filename

    response = requests.get(full_url, headers=request_header)

    if response.status_code == 404:
        logging.info('nwm ' + nwm_var_mod_type + ' model for ' + model_dt_str + ' not avilable (404 error).  URL: ' + full_url)
    else:
        logging.info('nwm ' + nwm_var_mod_type + ' model for ' + model_dt_str + ' succesfully downloaded.  URL: ' + full_url)

    return response, full_url, nwm_var_mod_type

def get_mod_df(now_utc, mod_type, request_header, config_vals):
    """
    will get most recent model run
    """
    # Posted model run is 6 hrs prior to cardinal time 6-hr time.  Posting time is a few minutes prior to 6-hr cardinal time.
    # for example, model run at 12z is posted at 17:53z.  Assumes cron runs script after 6-hr cardinal time (so about 2 time steps).
    # Similar is the case for short range
    if mod_type == 'medium': # only evaluating medium range blend
        model_time = now_utc.floor('6h') - pd.Timedelta(hours=12)
    elif mod_type == 'short':
        model_time = now_utc.floor('1h') - pd.Timedelta(hours=1)
    
    response, full_url, nwm_var_mod_type = get_url_response(model_time, mod_type, request_header, config_vals)
    
    # if file download exists, convert netcdf to dataframe
    # https://github.com/pydata/xarray/issues/1075
    temp_fn = os.path.splitext(os.path.basename(full_url))[0] + '.nc'
    temp_fullfn = os.path.join(out_dir, temp_fn)
    
    nc4_ds = netCDF4.Dataset(temp_fullfn, memory=response.content)
    store = xr.backends.NetCDF4DataStore(nc4_ds)

    xa = xr.open_dataset(store)
    nc_df = xa.to_dataframe()

    return nc_df, model_time, nwm_var_mod_type

def make_csv(df, config_vals, mod_dt, nwm_var_mod_type):
    '''
    csv cols:   lid,
                pe,
                dur (0),
                ts,
                extremum (Z),
                probability (-1 short/50 medium),
                validtime, 
                basistime, 
                value, 
                shef_qual_code (Z), 
                quality_code (1879048191, optional?),
                revision (0/1), 
                product_id
    '''
    pedtsep = config_vals['nwm_var_meta'][nwm_var_mod_type][config_vals['nwm_var']]

    if pedtsep[2] == 'I':
        dur = 0

    try:
        if pedtsep[6] == 'M':
            prob = -0.05   # shef manual, pg H-2 
    except:
        prob = -1.0

    return_df = pd.DataFrame()
    return_df['lid'] = df['lid']
    return_df['pe'] = pedtsep[0:2]
    return_df['dur'] = dur
    return_df['ts'] = pedtsep[3:5]
    return_df['extremum'] = pedtsep[5]
    return_df['probability'] = prob
    return_df['valid_time'] = df['time']
    return_df['basis_time'] = mod_dt
    return_df['value'] = df[config_vals['nwm_var']]
    return_df['shef_qual_code'] = 'Z'
    return_df['quality_code'] = 1879048191
    return_df['revision'] = 0
    return_df['product_id'] = config_vals['outputFileHeaderLines']['line2']

    return return_df



def main():
    # loop through mode (combined water level and surge)
    arg_vals = parse_args()
    utc_now = pd.Timestamp.utcnow().tz_localize(None) 

    config_vals = load_config_states('config')
    request_header = {'User-Agent' : config_vals['user_agent_pre'] + ' ' + config_vals['rfc_id'] + 'RFC'}
    map_df = map_ids(config_vals, request_header)
    mod_df, mod_dt, nwm_var_mod_type = get_mod_df(utc_now, arg_vals.mod, request_header, config_vals)

    mod_select_df = mod_df.copy().reset_index()[['station_id', 'time', config_vals['nwm_var']]]

    merged_df = map_df.merge(mod_select_df.copy())
    merged_df['streamflow'] = round(merged_df['streamflow']  * pow(100, 3) / pow(2.54, 3) / pow(12, 3), 2) # units & round
    
    if out_fmt == 'csv':
        csv_df = make_csv(merged_df, config_vals, mod_dt, nwm_var_mod_type)
        producttime = pd.Timestamp.utcnow().tz_localize(None)

    pdb.set_trace()
    






    logging.info('NWM download to shef started at ' + utc_now.strftime('%Y-%m-%d_%H:%M:%S'))

    nc_df, valid_model_dt = get_mod_df(utc_now, param, param_str)


if __name__ == '__main__':
    main()

