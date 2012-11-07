#!/usr/local/python/bin/python2.7 -u
import os
import traceback
os.environ['EPICS_BASE']='/beamline/epics/base/'
os.environ['EPICS_HOST_ARCH']='linux-x86_64'

import time
import sys
from threading import Thread
import redis
from epics import PV
from LogLine import LogLine
from DatFile import DatFile
from SimpleDaemon import SimpleDaemon
import cPickle as pickle

class LogWatcherRedis():
    """
    An object that watches the specified log file for changes to the log lines,
    it returns every new line
    """
    def __init__(self):
        self.redis = redis.StrictRedis(host='10.138.11.70', port=6379, db=0)
        self.LogPV = PV('13PIL1:logwriter1:FullFileName_RBV',callback=self.onFileNameChange)
        self.ProfilePV = PV('13PIL1:integrate1:Profile',callback=self.onNewProfile)
        self.QVectorPV = PV('13PIL1:integrate1:QVECTOR')
        self.filenamePV =PV('13PIL1:integrate1:FullFileName_RBV')
        self.log = ""
        self.name = "LogWatcherRedis"
        self.logLocation = ""
        self.alive = True
        self.thread = None

    def publishProfileThread(self, profile):
        qVector = self.QVectorPV.get()
        qVector = qVector[0:20]+qVector[20:40:2]+qVector[40:60:5]+qVector[60::15]
        profile = profile[0:20]+profile[20:40:2]+profile[40:60:5]+profile[60::15]
        filename = self.filenamePV.get(as_string=1)
        data = zip(qVector,profile)
	message = pickle.dumps({'filename':filename,'profile':data})
        print 'publish'
	self.redis.publish('logline:pub:raw_dat', message)
	self.redis.set('logline:raw_dat', message)
  
    def onNewProfile(self, pvname, value, **kwargs):
        thread=Thread(target=self.publishProfileThread, args=(value,))
        thread.daemon = True
	thread.start()
	
    def onFileNameChange(self, pvname, value, char_value, **kwargs):
        """
        Epics Callback Method
        """
        self.setLocation(char_value)
    
    def setLogPV(self, LogPVString):
        """
        Set the pv for the logfile location
        """
        self.LogPV.disconnect()
        self.LogPV = PV(LogPVString,callback=self.onFileNameChange)
    
    def setLocation(self, logLocation):
        """
        Sets location of the where the log file is that we want to watch
        """
        if (logLocation != self.logLocation):
            self.kill()
            self.logLocation = logLocation
            self.redis.set('logline:path', self.logLocation)
            self.watch()

    def pushNewLineRedis(self, line):
        """
        Spits logline data into redis
        """
        try:
            lineDict = LogLine(line)
            num = self.redis.incr('logline:num')
            self.redis.hmset('logline:%s' % (num,),lineDict.data)
            self.redis.lpush('logline:queue','logline:%s' % (num,))
            if (lineDict.data['SampleType'] == '8' and lineDict.data['ImageCounter'] == '1') :
                imageLocation = lineDict.data['ImageLocation']
                fileName, void = os.path.splitext(os.path.basename(imageLocation))
                datfilename = os.path.join(os.path.dirname(os.path.dirname(imageLocation)), 'raw_dat/%s.dat' % fileName)
                datfile = DatFile(datfilename)
                q = datfile.getq()
                p = datfile.getIntensities()
		qVector = q[0:20]+q[20:40:2]+q[40:60:5]+q[60::15]
                profile = p[0:20]+p[20:40:2]+p[40:60:5]+p[60::15]
                data = zip(qVector,profile)
	        message = pickle.dumps({'filename':fileName,'profile':data})
                self.redis.lpush('logline:autowater','logline:autowater:profile:%s' % (num,))
                self.redis.set('logline:autowater:profile:%s' % (num,),message)
                self.redis.publish('logline:pub:autowater',message)

        except Exception, err:
            print err
            
        #    print 'Error updating logline data. The line I got was: %s' % (line)
    
    def kill(self):
        """
        Used to kill the current log watcher thread, used it we need to restart/change user
        """
        self.alive = False
        if self.thread:
            self.thread.join()
    
    def watch(self):
        """
        Starts a thread that watches the logfile for changes
        """
        self.thread = Thread(target=self.watchThread,)
        self.thread.daemon = True
	self.thread.start()
    
    def fileWatch(self):
        """
        Here we watch constantly for a new line to be created
        """
        logfile = self.logLocation
        print "Waiting for: %s" % logfile

        start_time = time.time()
        while self.alive:
            try:
                fp = open(logfile,'r')
                print fp
                break
            except IOError:
                time.sleep(0.5);
            finally:
                if time.time()-start_time > 30.0: 
                    print "Timeout waiting for: %s" % logfile
                    return                
        if self.alive:
            print "Got logfile: %s" % logfile 
        else:
            print "Killed while waiting for: %s" % logfile 
            return
            
        while self.alive:
            new = fp.readline()
            if new:
                yield new
            else:
                time.sleep(0.5)

    def watchThread(self):
        """
            This returns every new line back up to the call back
        """
        self.alive = True
        for line in self.fileWatch():
            self.pushNewLineRedis(line)

class LogWatcherRedisDaemon(SimpleDaemon):
    # daemon method
    def run(self):
        from LogWatcherRedis import LogWatcherRedis
        a = LogWatcherRedis()
        while True:
            time.sleep(0.1)
        
        print 'Done'

if __name__ == "__main__":
    LogWatcherRedisDaemon()
    



