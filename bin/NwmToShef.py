from urllib.request import urlopen
import json, os, sys, time
from datetime import datetime, timedelta

#YAML included with the project, remove the yaml diretory if the module is loaded
import yaml


os.chdir(sys.path[0]+"/..")


#### Load the config file ####
try:
    stream = open('etc/NwmToShef.config', 'r')	
    config = yaml.safe_load(stream)
except IOError:
    print("No config file, 'cp doc/NwmToShef.config.example etc/NwmToShef.config' and edit as required.")
    sys.exit()

#### Initialize a few  variables ####
startTime = time.perf_counter()
timeFormat = "%Y-%m-%d %H:%M:%S" 
sites = config["sites"]
extrap = config["extrapolation"]
forecastStates = {}
forecastStates["latestForecastTimes"] = {}
nwmLookup = {}
nwmLookup["nwslid2nwm"] = {}
shefData = ""
sitesWithData = 0
outputFile =  config["outputFileName"].replace("<TIMESTAMP>",datetime.now().strftime("%Y%m%d%H%M"))


	

if not os.path.exists('etc/ratings'):
    os.makedirs('etc/ratings')

#### Setup the output File ####
for line in config["outputFileHeaderLines"]:
    if config["outputFileHeaderLines"][line]:
        shefData = shefData + config["outputFileHeaderLines"][line]+"\n"
    else:
        shefData = shefData + "\n"
shefData = shefData.replace("<TIMESTAMP>",datetime.now().strftime(timeFormat))
shefData = shefData.replace("@@@@@@",datetime.now().strftime("%d%H%M"))

if extrap:
    print("Stage values will be extrapolated")
else:
    print("Stage values will be set missing (-9999) if not within the limits of rating curve")
    shefData = shefData + ": Flow values above/below the rating curve will be set as -9999 for stage\n\n"




	
#### Load the last forecast issuance time states file ####
try:
    stream = open('etc/NwmToShef.state', 'r')
    forecastStates = yaml.safe_load(stream)
except IOError: 
    print("NWM state file does not exist will create a file NWMshef.state")

#### Load the NWSLID to NWM Mapping File ####
try:
    stream = open('etc/NWSlid2NWM.mapping', 'r')
    nwmLookup = yaml.safe_load(stream)
except IOError: 
    print("NWSLID to NWM mapping file does not exist will create a file NWSlid2NWM.mapping")



def interp(x_arr, y_arr, x,extrap = True):

    for i, xi in enumerate(x_arr):
        if xi >= x:
            break
    else:
        stage = y_arr[i] + (x - x_arr[i])*((y_arr[i] - y_arr[i-1])/(x_arr[i] - x_arr[i-1]))
        if extrap:
            print("   Discharge value: "+str(x)+" above the rating curve. Extrapolated stage: "+str(stage))
            return stage
        else: 
            return -9999

    if i == 0:
        stage = y_arr[0] + (x - x_arr[0])*((y_arr[1] - y_arr[0])/(x_arr[1] - x_arr[0]))
        if extrap:
            print("   Discharge value: "+str(x)+" below the rating curve. Extrapolated stage: "+str(stage))
            return stage
        else:
            return -9999

    x_min = x_arr[i-1]
    y_min = y_arr[i-1]
    y_max = y_arr[i]
    factor = (x - x_min) / (xi - x_min)


    return y_min + (y_max - y_min) * factor
    
    
    
def ratingConversion(stage,discharge,rating,extrap):

	
	stageValues = []
	flowValues = []
	counter = 0
	
	for item in rating['data']:		
		stageValues.append(item.get('stage'))
		flowValues.append(item.get('flow'))


	#Consider checking to make sure the arrays are sorted, return missing if not
	
	stage = interp(flowValues, stageValues, discharge,extrap)
	
	#print("Stage: "+str(stage))
	
	return stage
	

def getNWPSrating(nwslid,ratingAge = 7):

	if os.path.isfile('etc/ratings/'+nwslid): 
		file_mod_time = datetime.fromtimestamp(os.path.getmtime('etc/ratings/'+nwslid))
		today = datetime.today()
		age = today - file_mod_time
		if age.days > ratingAge:
			print("   Rating is "+str(age.days)+" days old and will be updated")
		else:
			print("   Using rating cached on: "+file_mod_time.strftime("%Y-%m-%d %H:%M"))
			f = open('etc/ratings/'+nwslid)
			rating_json = json.load(f)
			return rating_json
	else:
		print("   No cached rating available, downloading new rating")

	requestURL = config["NWPSapi"]+'gauges/'+site+'/ratings?onlyTenths=true'
	try:
		response = urlopen(requestURL)
	except IOError:
		#print(response)
		print("   Failed to get rating for "+nwslid+" at:"+requestURL)

	rating_json = json.loads(response.read())
	if 'data' not in rating_json:
		print("   No rating available from the NWPS rating endpoint at"+requestURL)

	with open('etc/ratings/'+nwslid, 'w') as f:
		f.write(json.dumps(rating_json, indent=4))

	return rating_json



# Simple function to convert NWM data services into .A shef formatted data
# Future: need to develop a .B format as well
def NwmToShef(nwslid,pedts,NWMjson,rating_json,extrap):
	precision = 4
	shef = ""
	shefStage = False
	forecastT0 = datetime.strptime(NWMjson["series"]["referenceTime"], "%Y-%m-%dT%H:%M:%SZ")
	DC = forecastT0.strftime("%Y%m%d%H%M")
	dataPairs = {}
	
	if "stage" in pedts:
		rating_json = getNWPSrating(nwslid,config["ratingCurveAge"])
		if 'data' in rating_json:
			print("   Include stage in shef file")
			shefStage = True
		else:
			print("   Do not include stage in shef file")
			
	
		
	for data in NWMjson["series"]["data"]:
		forecastTime = datetime.strptime(data["validTime"], "%Y-%m-%dT%H:%M:%SZ")
		fcstTime = forecastTime.strftime("%m%d Z DH%H%M")
		if "flow" in pedts:
			shef = shef + ".A "+nwslid.upper()+" "+fcstTime+"/DC"+DC+"/"+pedts["flow"]+"/"+str('{:.{precision}f}'.format(data["flow"]/1000,precision=precision))+"\n"
		if shefStage:
			stage = None
			stage = ratingConversion(stage,data["flow"],rating_json,extrap)
			shef = shef + ".A "+nwslid.upper()+" "+fcstTime+"/DC"+DC+"/"+pedts["stage"]+"/"+str('{:.{precision}f}'.format(stage,precision=2))+"\n"

	return shef

# Main loop to iterate through forecasts types and NWS sites
for site in sites:
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
		

	
			
					
	#Get the National Water Model Data	
	requestURL = config["NWPSapi"]+"reaches/"+nwmReachId+"/streamflow"
	print("   Downloading NWM Guidance: "+requestURL)
	try:
		response = urlopen(requestURL)
	except IOError:
		#print(response)
		print("  Failed to get data for "+site.upper()+" at:"+requestURL)
		continue
		
	data_json = json.loads(response.read())	
	
	for NWMguidance in config["NWMrequests"] :
		forecast = data_json[NWMguidance];
		shefCodes = config["NWMrequests"][NWMguidance]
		forecastT0 = datetime.strptime(forecast["series"]["referenceTime"], "%Y-%m-%dT%H:%M:%SZ")
		
		if NWMguidance not in forecastStates["latestForecastTimes"]:
			forecastStates["latestForecastTimes"][NWMguidance] = {}
		if site.upper() in forecastStates["latestForecastTimes"][NWMguidance]:
			lastUpdateT0 = forecastStates["latestForecastTimes"][NWMguidance][site.upper()]
		else:
			lastUpdateT0 = datetime.today() - timedelta(days = 2)
					
		if forecastT0 > lastUpdateT0 or config["forceShefEncode"] == True :
			forecastStates["latestForecastTimes"][NWMguidance][site.upper()] = forecastT0
			shefData = shefData + NwmToShef(site,shefCodes,forecast,rating_json,extrap)
			print("   Shef encoded "+NWMguidance+" for site: "+site.upper()+" current forecast issuance: "+forecastT0.strftime(timeFormat))
			sitesWithData = sitesWithData + 1
	
		else:
			print("   Skipped "+NWMguidance+" for site: "+site.upper()+" current forecast: "+forecastT0.strftime(timeFormat)+" previous forecast:"+lastUpdateT0.strftime(timeFormat))	



if sitesWithData > 0:
    with open(config['outputLocation']+"/"+outputFile, 'w') as f:
        f.write(shefData)
else:
    print("No new shef data to encode.")

with open("etc/NwmToShef.state", 'w+') as yaml_file:
    yaml_file.write( yaml.dump(forecastStates, default_flow_style=False))
    
with open("etc/NWSlid2NWM.mapping", 'w+') as yaml_file:
    yaml_file.write( yaml.dump(nwmLookup, default_flow_style=False))

endTime = time.perf_counter()
print(f"NWM2Shef runtime {endTime - startTime :0.4f} seconds")





  
  




