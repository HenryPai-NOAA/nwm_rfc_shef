#!/awips2/python/bin/python

# poc:          henry pai
# last edit:    feb 2025 
# last edit:    hp, feb 2025
# edit notes:   usbr scraper rewrite

# 
# https://nomads.ncep.noaa.gov/pub/data/nccf/com/nwm/post-processed/RFC/NW/channel_rt/



import os, json, argparse, pathlib, urllib, netCDF4, requests, yaml, logging, sys, pdb
import xarray as xr
import pandas as pd
import numpy as np

os.umask(0o002)

# === global var (not path related)
# NWRFC settings

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

config_fn = 'NwmToShef.config'
state_fn = 'NwmToShef.state'
mapping_fn = 'NWSlid2NWM.mapping'
log_fn = 'nwm_download.log'

# ===== url info
nwm_base_url = 'https://nomads.ncep.noaa.gov/pub/data/nccf/com/nwm/post-processed/RFC/NW/channel_rt/'
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

def get_url_response(model_time, current_model_bool, param, param_str):
    """
    generates url and does some url checking
    returns response
    """
    model_day_str = model_time.strftime('%Y%m%d')
    model_hr_str = model_time.strftime('%H')
    model_dt_str = model_time.strftime('%Y-%m-%d %HZ')
    full_url = nwm_base_url + nwm_pre + model_day_str + "/" + stofs_mod_pre + "t" + model_hr_str + stofs_fn_points + param + ".nc"

    http = urllib3.PoolManager(cert_reqs='CERT_NONE')
    #response = http.request('GET', full_url, headers=requests_header)
    response = requests.get(full_url, headers=requests_header)

    #pdb.set_trace()

    if response.status_code == 404 and current_model_bool == True:
        logging.info('NOS STOFS ' + param_str + ' model for ' + model_dt_str + ' not avilable (404 error).  URL: ' + full_url)
    elif response.status_code == 404 and current_model_bool == False:
        logging.info('NOS STOFS ' + param_str + ' model for prior timestep at ' + model_dt_str + ' not avilable (404 error).  URL: ' + full_url)
    else:
        logging.info('NOS STOFS ' + param_str + ' model for ' + model_dt_str + ' succesfully downloaded, url: ' + full_url)

    return response, full_url, model_time

def get_mod_df(now_utc, param, param_str):
    """
    will get most recent model run, or if most recent, get the one prior to that
    returns netcdf df and downloaded valid run time
    """
    # Posted model run is 6 hrs prior to cardinal time 6-hr time.  Posting time is a few minutes prior to 6-hr cardinal time.
    # for example, model run at 12z is posted at 17:53z.  Assumes cron runs script after 6-hr cardinal time
    model_time = now_utc.floor('6h') - pd.Timedelta(hours=6) 
    
    response, full_url, model_dt = get_url_response(model_time, True, param, param_str)
    
    # if file download exists, convert netcdf to dataframe
    # https://github.com/pydata/xarray/issues/1075
    temp_fn = fname = os.path.splitext(os.path.basename(full_url))[0] + '.nc'
    temp_fullfn = out_dir + temp_fn
    
    nc4_ds = netCDF4.Dataset(temp_fullfn, memory=response.content)
    store = xr.backends.NetCDF4DataStore(nc4_ds)

    xa = xr.open_dataset(store)
    nc_df = xa.to_dataframe()

    return nc_df, model_dt

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
    
    with open(os.path.join(meta_dir, config_fn)) as stream:
        try:
            yaml_stream = yaml.safe_load(stream)
        except IOError:
            if file_type == 'config':
                logging.info("No config file, 'cp doc/NwmToShef.config.example etc/NwmToShef.config' and edit as required.")
                sys.exit()
            else:
                logging.info('NWM ' + file_type  + ' file does not exist will create a file' + fn)

    return(yaml_stream)

def map_ids(config):

    nwmLookup = {}
    nwmLookup["nwslid2nwm"] = {}
    nwmLookup = load_config_states('mapping')

    for site in config['sites']:
        site = site.upper();
        print("Working on "+site)
        rating_json = {}
        
        if site not in nwmLookup["nwslid2nwm"]:
            requestURL = config["NWPSapi"]+'gauges/'+site
            try:
                response = urlopen(requestURL)
            except IOError:
                #print(response)
                print("  Failed to get metadata for "+site.upper()+" at:"+requestURL)
                continue					
        
            data_json = json.loads(response.read())	
            nwmReachId = data_json["reachId"]
            print("   New NWM reachId:"+nwmReachId)
            nwmLookup["nwslid2nwm"][site.upper()] = nwmReachId
        else:
            nwmReachId = nwmLookup["nwslid2nwm"][site.upper()]    
            print("   Cached NWM reachId:"+nwmReachId)



def main():
    # loop through mode (combined water level and surge)
    arg_vals = parse_args()
    utc_now = pd.Timestamp.utcnow().tz_localize(None) # using pandas for some additional functionality; localize to none for indexing purposes

    config_vals = load_config_states('config')

    pdb.set_trace()
    mapped_ids = map_ids(config_vals) 






    logging.info('NWM download to shef started at ' + utc_now.strftime('%Y-%m-%d_%H:%M:%S'))

    nc_df, valid_model_dt = get_mod_df(utc_now, param, param_str)


if __name__ == '__main__':
    main()

