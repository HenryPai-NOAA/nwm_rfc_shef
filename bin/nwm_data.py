#!/awips2/python/bin/python

"""
Script to grab National Water Model output
Originally developed by John Lhotak of CBRFC
Modified for use at NWRFC by Taylor Dixon
"""

import sys, os, optparse, shutil, glob
import datetime as dt
from subprocess import Popen,PIPE,STDOUT

os.umask(0o002)

p = optparse.OptionParser()
p.add_option('--rfc'            , '-r', dest="rfc"                              , default='nwrfc', help='rfc 5 char id'+'[default: %default]')
p.add_option('--locdir'         , '-d', dest="localDir"                         , default=None   , help='local directory to store netcdf files')
p.add_option('--date'           , '-z', dest="nwmDate"                          , default=None   , help='netcdf file date to retrieve fmt: %Y%m%d%H')
p.add_option('--type'           , '-t', dest="nwmType"                          , default='short', choices=['short','medium','long','assim'],help='forecast type short, medium, long or assim')
p.add_option('--log_to_file_off', '-l', dest="log_to_file", action="store_false", default=True   , help='have print statements go to to terminal instead of file')
opts, args = p.parse_args()

if opts.log_to_file == True:
    log = open('/data/ldad/logs/nwm/nwm_'+opts.nwmType+'.log','w')
    sys.stdout = log
    sys.stderr = log

print('National Water Model Output retrieval')

#Where to get the files
hostName = 'http://nomads.ncep.noaa.gov'
hostIP   = 'http://140.90.101.62'
pubDir   = '/pub/data/nccf/com/nwm/post-processed/RFC/'+opts.rfc[:2].upper()
chnrtDir = pubDir+'/channel_rt/'
#feDir = pubDir+'/fe/'
#landDir = pubDir+'/land/'
ldadDir  = '/data/Incoming'
ldadNwm  = '/data/ldad/nwm'

print("%-10s: %s" %('host',hostIP))
print("%-10s: %s" %('pub dir',pubDir))

#check localdir 
if opts.localDir  == None:
    localDir = '/data/ldad/nwm'
else:
    if os.path.exists(opts.localDir):
        os.chdir(opts.localDir)
        localDir = os.getcwd()
    else:
        sys.exit('local dir path: '+opts.localDir+' does not exists')

print("%-10s: %s" %('local dir',localDir))
    
if os.path.exists('channel_rt') == False:
    os.mkdir('channel_rt')
#if os.path.exists('fe') == False:
    #os.mkdir('fe')
#if os.path.exists('land') == False:
    #os.mkdir('land')

def roundTime(dT=None,dateDelta=dt.timedelta(minutes=1)):
    roundT0 = dateDelta.seconds
    seconds = (dT - dT.min).seconds
    rounding = (seconds+roundT0/2)//roundT0*roundT0
    return dT + dt.timedelta(seconds=rounding-seconds)

# set data latencies
if opts.nwmType == 'assim':
    deltaList = [1,2,3]
elif opts.nwmType == 'short':
    deltaList = [2,3]
elif opts.nwmType == 'medium':
    deltaList = [6]
elif opts.nwmType == 'long':
    deltaList = [6,12,18,24,30,36,42,48]

for delta in deltaList:
    ## set file date and name
    if opts.nwmDate == None:
        if opts.nwmType == 'assim':
            nwmFlowDate = (dt.datetime.now() - dt.timedelta(hours=delta) ).strftime("nwm.t%Y%m%d%Hz")
            #nwmForcDate = (dt.datetime.now() - dt.timedelta(hours=2) ).strftime("nwm.t%Y%m%d%Hz")
            #nwmLandDate = (dt.datetime.now() - dt.timedelta(hours=2) ).strftime("nwm.t%Y%m%d%Hz")
        elif opts.nwmType == 'short':
            nwmFlowDate = (dt.datetime.now() - dt.timedelta(hours=delta) ).strftime("nwm.t%Y%m%d%Hz")
            #nwmForcDate = (dt.datetime.now() - dt.timedelta(hours=2) ).strftime("nwm.t%Y%m%d%Hz")
        elif opts.nwmType == 'medium':
            sixhourTime = roundTime((dt.datetime.now() - dt.timedelta(hours=delta)),dt.timedelta(hours=6))
            nwmFlowDate = sixhourTime.strftime("nwm.t%Y%m%d%Hz")
            #nwmForcDate = sixhourTime.strftime("nwm.t%Y%m%d%Hz")
        elif opts.nwmType == 'long':
            #sixhourFlowTime = roundTime((dt.datetime.now() - dt.timedelta(hours=delta)),dt.timedelta(hours=6))
            sixhourTime = roundTime((dt.datetime.now() - dt.timedelta(hours=delta)),dt.timedelta(hours=6))
            #nwmFlowDate = sixhourFlowTime.strftime("nwm.t%Y%m%d%Hz")
            nwmFlowDate = sixhourTime.strftime("nwm.t%Y%m%d%Hz")
            #sixhourForcTime = roundTime((dt.datetime.now() - dt.timedelta(hours=24)),dt.timedelta(hours=6))
            #nwmDate = sixhourForcTime.strftime("nwm.t%Y%m%d%Hz")

    ## make file name
    if opts.nwmType == 'assim':
        channel_rtFile1 = nwmFlowDate+'.analysis_'+opts.nwmType+'.channel_rt.tm01.'+opts.rfc.lower()+'.nc'
        channel_rtFile2 = nwmFlowDate+'.analysis_'+opts.nwmType+'.channel_rt.tm02.'+opts.rfc.lower()+'.nc'
        #feFile1 = nwmForcDate+'.analysis_'+opts.nwmType+'.forcing.tm01.'+opts.rfc.lower()+'.nc'
        #feFile2 = nwmForcDate+'.analysis_'+opts.nwmType+'.forcing.tm02.'+opts.rfc.lower()+'.nc'
        #landFile = nwmLandDate+'.analysis_'+opts.nwmType+'.land.tm02.'+opts.rfc.lower()+'.nc' 

    elif opts.nwmType == 'short':
        channel_rtFile = nwmFlowDate+'.'+opts.nwmType+'_range.channel_rt.'+opts.rfc.lower()+'.nc'
        #feFileList = []
        #for r in range(1,10):
        #        feFile = nwmForcDate+'.'+opts.nwmType+'_range.forcing.f00'+str(r)+'.'+opts.rfc.lower()+'.nc'
        #        feFileList.append(feFile)
        #for r in range(10,19):
        #        feFile = nwmForcDate+'.'+opts.nwmType+'_range.forcing.f0'+str(r)+'.'+opts.rfc.lower()+'.nc'
        #        feFileList.append(feFile)

        feFile = 'junk'
        landFile = 'junk'

    elif opts.nwmType == 'medium':
        channel_rtFile1 = nwmFlowDate+'.'+opts.nwmType+'_range.channel_rt_1.'+opts.rfc.lower()+'.nc'
        channel_rtFile2 = nwmFlowDate+'.'+opts.nwmType+'_range.channel_rt_2.'+opts.rfc.lower()+'.nc'
        channel_rtFile3 = nwmFlowDate+'.'+opts.nwmType+'_range.channel_rt_3.'+opts.rfc.lower()+'.nc'
        channel_rtFile4 = nwmFlowDate+'.'+opts.nwmType+'_range.channel_rt_4.'+opts.rfc.lower()+'.nc'
        channel_rtFile5 = nwmFlowDate+'.'+opts.nwmType+'_range.channel_rt_5.'+opts.rfc.lower()+'.nc'
        channel_rtFile6 = nwmFlowDate+'.'+opts.nwmType+'_range.channel_rt_6.'+opts.rfc.lower()+'.nc'
        channel_rtFile7 = nwmFlowDate+'.'+opts.nwmType+'_range.channel_rt_7.'+opts.rfc.lower()+'.nc'
        
        #feFileList = []
        #for r in range(1,10,1):
        #        feFile = nwmForcDate+'.'+opts.nwmType+'_range.forcing.f00'+str(r)+'.'+opts.rfc.lower()+'.nc'
        #        feFileList.append(feFile)
        #for r in range(10,100,1):
        #        feFile = nwmForcDate+'.'+opts.nwmType+'_range.forcing.f0'+str(r)+'.'+opts.rfc.lower()+'.nc'
        #        feFileList.append(feFile)
        #for r in range(100,241,1):
        #        feFile = nwmForcDate+'.'+opts.nwmType+'_range.forcing.f'+str(r)+'.'+opts.rfc.lower()+'.nc'
        #        feFileList.append(feFile)

        feFile = 'junk'
        landFile = 'junk'
    
    elif opts.nwmType == 'long':
        channel_rtFile1 = nwmFlowDate+'.'+opts.nwmType+'_range.channel_rt_1.'+opts.rfc.lower()+'.nc'
        channel_rtFile2 = nwmFlowDate+'.'+opts.nwmType+'_range.channel_rt_2.'+opts.rfc.lower()+'.nc'
        channel_rtFile3 = nwmFlowDate+'.'+opts.nwmType+'_range.channel_rt_3.'+opts.rfc.lower()+'.nc'
        channel_rtFile4 = nwmFlowDate+'.'+opts.nwmType+'_range.channel_rt_4.'+opts.rfc.lower()+'.nc'
        feFile = 'junk'
        landFile = 'junk'

    ## make file lists
    if opts.nwmType == 'assim':
        channel_rtFileList = [channel_rtFile1,channel_rtFile2]
        #feFileList = [feFile1,feFile2]
        #landFileList = [landFile]    
    
    elif opts.nwmType == 'short':
        channel_rtFileList = [channel_rtFile]
        #feFileList = feFileList
        #landFileList = [landFile]

    elif opts.nwmType == 'medium':
        channel_rtFileList = [channel_rtFile1,channel_rtFile2,channel_rtFile3,channel_rtFile4,channel_rtFile5,channel_rtFile6,channel_rtFile7]
        #feFileList = feFileList
        #landFileList = [landFile]
    
    elif opts.nwmType == 'long':
        channel_rtFileList = [channel_rtFile1,channel_rtFile2,channel_rtFile3,channel_rtFile4]
        #feFileList = [feFile]
        #landFileList = [landFile]
    
    #FileLists = [channel_rtFileList,feFileList,landFileList] 
    FileLists = [channel_rtFileList] 

    for FileList in FileLists:
        for dataFile in FileList:
                if 'channel' in dataFile:
                        dlDic = {'channel_rt':('channel_rt/',chnrtDir,dataFile)}
                        ncDir = 'channel_rt' 
                #elif 'forcing' in dataFile:
                        #dlDic = {'fe':('fe/',feDir,dataFile)}
                        #ncDir = 'fe'   
                #else:
                        #dlDic = {'land':('land/',landDir,dataFile)}
                        #ncDir = 'land'  

                for localSubDir,wgetDir,wgetFile in (dlDic[ncDir],):
                        os.chdir(localDir)
                        noNewFile = []
                        if 'junk' not in wgetFile:
                                wget = 'wget -np -nH -N -O '+wgetFile+' '+hostName+wgetDir+wgetFile
                                print("%-10s: %s" %('  wget cmd',wget))
                                os.chdir(localSubDir)
                                sys.stdout.flush()
                                wgetPopen = Popen(wget,stdout=PIPE,stderr=STDOUT,shell=True)
                                while wgetPopen.poll() == None:
                                        stline = wgetPopen.stdout.readline().strip()
                                        print("%-10s: %s" %('  ',stline))
                                        if 'Remote file no newer' in str(stline):
                                                noNewFile.append(stline.replace("\xe2\x80\x9c",'"').replace("\xe2\x80\x9d",'"').split('"')[1])
                                        sys.stdout.flush()
                                os.chdir(localDir)
                                sys.stdout.flush()

                        filesToCopy = glob.glob(localSubDir+wgetFile)
                        filesToCopy.sort()
                        for f in filesToCopy:
                                if os.path.getsize(f) > 0:
                                        if f.split('/')[1] not in noNewFile:
                                                print("%-10s: %s" %('copying',f))
                                                shutil.copy(f,ldadDir)                        
                                        else:
                                                print("%-10s: %s" %('notcopying',f))
                                else:
                                        print("%-10s: %s" %('0 byte file, so notcopying',f))
                        sys.stdout.flush()

os.chdir(localDir)

ncDir = 'channel_rt/'
print("%-10s: %s" %('clean up',ncDir+' - '+str(dt.datetime.now())))
fileList = os.listdir(ncDir)
fileList.sort()
for f in fileList:
    fctime  = [dt.datetime.fromtimestamp(d) for d in os.stat(ncDir+f)[-3:]]
    if fctime[1] < (dt.datetime.now() - dt.timedelta(days=5)):
        print("%-10s: %s %s" %(' ','removing',f))
        try: os.remove(ncDir+f)
        except: print("%-10s: %s" %(' ','*** removal failed ***'))

##################################################################

#Duplicating retrieval script for test data
#if opts.log_to_file == True:
#    log = open('/data/ldad/logs/nwm_'+opts.nwmType+'.test.log','w')
#    sys.stdout = log
#    sys.stderr = log
#
#print('National Water Model Output retrieval')
#
##Where to get the files
#hostNameTest = 'http://nomads.ncep.noaa.gov'
#hostIPTest   = 'http://140.90.101.62'
#pubDirTest   = '/pub/data/nccf/nonoperational/nwm/RFC/'+opts.rfc[:2].upper()
#chnrtDir = pubDirTest+'/channel_rt/'
#ldadDir  = '/data/Incoming'
#ldadNwm  = '/data/ldad/nwm'
#
#print("%-10s: %s" %('host',hostIPTest))
#print("%-10s: %s" %('pub dir',pubDirTest))
#
#if opts.localDir  == None:
#    localDir = ldadNwm
#else:
#    if os.path.exists(opts.localDir):
#        os.chdir(opts.localDir)
#        localDir = os.getcwd()
#    else:
#        sys.exit('local dir path: '+opts.localDir+' does not exists')
#
#print("%-10s: %s" %('local dir',localDir))
#    
#if os.path.exists('channel_rt/test') == False:
#    os.mkdir('channel_rt/test')
#
#def roundTime(dT=None,dateDelta=dt.timedelta(minutes=1)):
#    roundT0 = dateDelta.seconds
#    seconds = (dT - dT.min).seconds
#    rounding = (seconds+roundT0/2)//roundT0*roundT0
#    return dT + dt.timedelta(seconds=rounding-seconds)
#
#if opts.nwmType == 'assim':
#    deltaList = [1,2,3]
#elif opts.nwmType == 'medium':
#    #deltaList = [6]    
#    deltaList = [6,12,18,24,30,36,42,48]
#
#for delta in deltaList:
#    ## set file date and name for channel_rt
#    if opts.nwmDate == None:
#        if opts.nwmType == 'assim':
#            nwmDate = (dt.datetime.now() - dt.timedelta(hours=delta) ).strftime("nwm.t%Y%m%d%Hz")
#        elif opts.nwmType == 'medium':
#            sixhourTime = roundTime((dt.datetime.now() - dt.timedelta(hours=delta)),dt.timedelta(hours=6))
#            nwmDate = sixhourTime.strftime("nwm.t%Y%m%d%Hz")
#    else:
#        try: nwmDate = dt.datetime.strptime(opts.nwmDate,"%Y%m%d%H").strftime("nwm.t%Y%m%d%Hz")  
#        except: sys.exit(opts.nwmDate+': not a valid date %Y%m%d%H')
#
#    ## make download file name
#    if opts.nwmType == 'assim':
#        channel_rtFile1 = nwmDate+'.analysis_'+opts.nwmType+'.channel_rt.tm01.'+opts.rfc.lower()+'.nc'
#        channel_rtFile2 = nwmDate+'.analysis_'+opts.nwmType+'.channel_rt.tm02.'+opts.rfc.lower()+'.nc'
#        channel_rtFileNoDa1 =  nwmDate+'.analysis_'+opts.nwmType+'_no_da.channel_rt.tm01.'+opts.rfc.lower()+'.nc'        
#        channel_rtFileNoDa2 =  nwmDate+'.analysis_'+opts.nwmType+'_no_da.channel_rt.tm02.'+opts.rfc.lower()+'.nc'
#        feFile = 'junk'    
#    elif opts.nwmType == 'short':
#        channel_rtFile = 'junk'
#        feFile = 'junk'
#    elif opts.nwmType == 'medium':
#        channel_rtFile1 = nwmDate+'.'+opts.nwmType+'_range.channel_rt_1.'+opts.rfc.lower()+'.nc'
#        channel_rtFile2 = nwmDate+'.'+opts.nwmType+'_range.channel_rt_2.'+opts.rfc.lower()+'.nc'
#        channel_rtFile3 = nwmDate+'.'+opts.nwmType+'_range.channel_rt_3.'+opts.rfc.lower()+'.nc'
#        channel_rtFile4 = nwmDate+'.'+opts.nwmType+'_range.channel_rt_4.'+opts.rfc.lower()+'.nc'
#        channel_rtFile5 = nwmDate+'.'+opts.nwmType+'_range.channel_rt_5.'+opts.rfc.lower()+'.nc'
#        channel_rtFile6 = nwmDate+'.'+opts.nwmType+'_range.channel_rt_6.'+opts.rfc.lower()+'.nc'
#        #channel_rtFile7 = nwmFlowDate+'.'+opts.nwmType+'_range.channel_rt_7.'+opts.rfc.lower()+'.nc'
#        channel_rtFile7 = nwmDate+'.'+opts.nwmType+'_range_blend.channel_rt.'+opts.rfc.lower()+'.nc'
#        channel_rtFileNoDa = nwmDate+'.'+opts.nwmType+'_range_no_da.channel_rt.'+opts.rfc.lower()+'.nc'
#        feFile = 'junk'
#    elif opts.nwmType == 'long':
#        channel_rtFile1 = 'junk'
#        channel_rtFile2 = 'junk'
#        channel_rtFile3 = 'junk'
#        channel_rtFile4 = 'junk'
#        feFile = 'junk'
#
#    if opts.nwmType == 'assim':
#        channel_rtFileList = [channel_rtFile1,channel_rtFile2,channel_rtFileNoDa1,channel_rtFileNoDa2]
#        feFileList = [feFile]
#    elif opts.nwmType == 'short':
#        channel_rtFileList = [channel_rtFile]
#        feFileList = [feFile]
#    elif opts.nwmType == 'medium':
#        channel_rtFileList = [channel_rtFile1,channel_rtFile2,channel_rtFile3,channel_rtFile4,channel_rtFile5,channel_rtFile6,channel_rtFile7,channel_rtFileNoDa]
#        feFileList = [feFile]
#    elif opts.nwmType == 'long':
#        channel_rtFileList = [channel_rtFile1,channel_rtFile2,channel_rtFile3,channel_rtFile4]
#        feFileList = [feFile]
#
#    FileLists = [channel_rtFileList,feFileList] 
#
#    for FileList in FileLists:
#        for dataFile in FileList:
#                if 'channel' in dataFile:
#                        dlDic = {'channel_rt':('channel_rt/test/',chnrtDir,dataFile)}
#                        ncDir = 'channel_rt' 
#                else:
#                        dlDic = {'fe':('fe/test/',feDir,dataFile)}
#                        ncDir = 'fe'     
#                for localSubDir,wgetDir,wgetFile in (dlDic[ncDir],):
#                        os.chdir(localDir)
#                        noNewFile = []
#                        if 'junk' not in wgetFile:
#                                wget = 'wget -np -nH -N -O '+wgetFile+'.test '+hostNameTest+wgetDir+wgetFile
#                                print("%-10s: %s" %('  wget cmd',wget))
#                                os.chdir(localSubDir)
#                                sys.stdout.flush()
#                                wgetPopen = Popen(wget,stdout=PIPE,stderr=STDOUT,shell=True)
#                                while wgetPopen.poll() == None:
#                                        stline = wgetPopen.stdout.readline().strip()
#                                        print("%-10s: %s" %('  ',stline))
#                                        if 'Remote file no newer' in str(stline):
#                                                noNewFile.append(stline.replace("\xe2\x80\x9c",'"').replace("\xe2\x80\x9d",'"').split('"')[1])
#                                        sys.stdout.flush()
#                                os.chdir(localDir)
#                                sys.stdout.flush()
#
#                        filesToCopy = glob.glob(localSubDir+wgetFile+'.test')
#                        filesToCopy.sort()
#                        for f in filesToCopy:
#                                if os.path.getsize(f) > 0:
#                                        if f.split('/')[1] not in noNewFile:
#                                                print("%-10s: %s" %('copying',f))
#                                                shutil.copy(f,ldadDir)                        
#                                        else:
#                                                print("%-10s: %s" %('notcopying',f))
#                                else:
#                                        print("%-10s: %s" %('0 byte file, so notcopying',f))
#                        sys.stdout.flush()
#
#os.chdir(localDir)
#
#for ncDir in ('channel_rt/test/','fe/test/'):
#        print("%-10s: %s" %('clean up',ncDir+' - '+str(dt.datetime.now())))
#        fileList = os.listdir(ncDir)
#        fileList.sort()
#        for f in fileList:
#                fctime  = [dt.datetime.fromtimestamp(d) for d in os.stat(ncDir+f)[-3:]]
#                if fctime[1] < (dt.datetime.now() - dt.timedelta(days=5)):
#                        print("%-10s: %s %s" %(' ','removing',f))
#                        try: os.remove(ncDir+f)
#                        except: print("%-10s: %s" %(' ','*** removal failed ***'))



