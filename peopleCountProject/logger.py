import os
import logging
import re
from logging.handlers import TimedRotatingFileHandler

class Logger():
    def __init__(self, logname="allLog", loglevel=logging.INFO, loggername=None, streamoutput=True):
        self.logger = logging.getLogger(loggername)  
        self.logger.setLevel(loglevel)
        logname += '.log'    
        log_path = os.path.join(os.getcwd() + "/logs", logname)
        
        if not os.path.exists(log_path):
            file = open(log_path,'w')
            file.close()
        
        file_handler = TimedRotatingFileHandler(filename=log_path, when="midnight", interval=1, backupCount=5)
        file_handler.suffix = "%Y-%m-%d.log"
        file_handler.extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}.log$")
        
        formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] - %(module)s.%(funcName)s (%(filename)s:%(lineno)d) - %(message)s"
            )
        file_handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            if streamoutput:
                stream_logger = logging.StreamHandler()
                stream_logger.setLevel(loglevel)
                self.logger.addHandler(stream_logger)
                  
            self.logger.addHandler(file_handler)
        
    def getlogger(self):
        return self.logger