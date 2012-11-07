#!/usr/bin/env python

import daemon, argparse, sys, os
from lockfile.pidlockfile import PIDLockFile

import pwd, grp

class IDConvert(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if values.isdigit():
            id_no = int(values)
        else:
            if(self.dest == 'uid'):
                id_no = pwd.getpwnam(values).pw_uid
                setattr(namespace, 'gid', pwd.getpwnam(values).pw_gid)
            elif(self.dest == 'gid'):
                id_no = pwd.getpwnam(values).pw_uid
            else:
                raise Exception('Unknown Destination: %s' % self.dest)
            
        setattr(namespace, self.dest, id_no)

class PIDFileAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):            
        setattr(namespace, self.dest, PIDLockFile(values))
class LogFileAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, open(values, 'a', 0))
        
class SimpleDaemon(object):
    def __init__(self, **kw):
        self.context = self._get_context() 
        self.context.__dict__.update(kw)
        
        if not self.context.start_as_daemon:
            self.context.detach_process = False
            
            if self.context.stdout == None:
                self.context.stdout = sys.stdout
                self.context.stderr = sys.stderr
                
            if self.context.stdin == None:
                self.context.stdin = sys.stdin

        # default directory fix
        if self.context.working_directory == unicode('/'):
            self.context.working_directory = unicode(os.getcwd())
        
        # default stderr to stdout
        if self.context.stderr == None:
            self.context.stderr = self.context.stdout

        self.setup(self.context)
        
        if self.context.pidfile:
            self.check()
            
#        try:
        with self.context:
            if self.context.title:
                self.set_title(self.context.title)
            self.run()
#        except Exception:
#            print "bad stuff happened..."
#            sys.exit(1)   
            
    def _get_context(self):
        parser = argparse.ArgumentParser(description='Python ADSC')
        parser.add_argument('-d', '--daemon', action='store_true', help='start as daemon', dest='start_as_daemon')
        parser.add_argument('--title', type=str, help='process title')
        parser.add_argument('--pidfile', type=str, help='pidfile location', action=PIDFileAction)
        parser.add_argument('--working-directory', type=unicode, help='working directory', dest='working_directory')
        parser.add_argument('--umask', type=int, help='creation mask')
        parser.add_argument('--uid', '-u', type=str, help='user', action=IDConvert)
        parser.add_argument('--gid', '-g', type=str, help='group', action=IDConvert)
        parser.add_argument('--stdout', type=str, help='stdout', action=LogFileAction)
        parser.add_argument('--stdin', type=str, help='stdin', action=LogFileAction)
        parser.add_argument('--stderr', type=str, help='stderr', action=LogFileAction)        
        
        context = daemon.DaemonContext()
        parser.parse_args(namespace=context)      
        return context
        
    def check(self): #check its not already running and remove statle pidfiles
        if self.context.pidfile.is_locked():
            pid = self.context.pidfile.read_pid()
            try:            
                os.kill(pid, 0)
            except OSError, err:
                err = str(err)
                if err.find("No such process") > 0:
                    self.context.pidfile.break_lock()
                else:
                    print str(err)
                    sys.exit(15)
            else:
                sys.exit(1)                    
        
    def setup(self, context):
        pass    
    def run(self):
        pass
        
    def set_title(self, title):
        try:
          import setproctitle
          setproctitle.setproctitle(title)
        except:
          pass # Ignore errors, since this is only cosmetic
          
          
class ExampleDaemon(SimpleDaemon):
#    init if required
#    def __init__(self):
#        SimpleDaemon.__init__(self, title='mydaemon')
    
#    hijack daemon conext
#    def setup(self, context):
#        context.pidfile = PIDLockFile('/tmp/mydaemon.pid')
        
    # daemon method
    def run(self):
        import time
        from datetime import datetime
        while True:
            print datetime.now()
            time.sleep(1.0)
        
if __name__ == '__main__':
    ExampleDaemon()   
