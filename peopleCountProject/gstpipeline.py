import configparser
import sys
sys.path.append("..")
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from ctypes import *
from gi.repository import GObject, Gst
from common.FPS import GETFPS
from common.is_aarch_64 import is_aarch64
from logger import Logger
from ast import literal_eval
import pyds


# 获取项目配置文件内容
class ProjectConfig:
    _isopen = False
    _config = configparser.ConfigParser()
    _urinum = 0
    logger = Logger().getlogger()

    def __init__(self, cfgfile):
        if len(self._config.read(cfgfile)):
            self._isopen = True
            self._config.sections()
        else:
            self.logger.critical("open config file error")
            
    def get_uri(self):
        if self._isopen:
            uri = []
            for key in self._config['URI']:
                uri.append(self._config.get('URI', key))
            self._urinum = len(uri)
            return uri
        else:
            return []
        
    def get_tiled_size(self):
        if self._isopen:
            size = []
            for key in self._config['TILED_OUTPUT_SIZE']:
                size.append(self._config.getint('TILED_OUTPUT_SIZE', key))
            return size
        else:
            return []
        
    def get_uri_num(self):
        return self._urinum
        
    def get_codec(self):
         if self._isopen:
                for key in self._config['CODEC']:
                    return self._config.get('CODEC', key)
    
    def get_udp_port(self):
         if self._isopen:
                for key in self._config['UDPSINKPORT']:
                    return self._config.getint('UDPSINKPORT', key)
                
    def get_rtsp_port(self):
         if self._isopen:
                for key in self._config['RTSPPORT']:
                    return self._config.getint('RTSPPORT', key)
    
    #return format --> {'pos_0':{'line_x':xx}, 'pos_1':{...} ....}            
    def get_line_osd_pos(self):
        dictpos = {}
        posorder = {}
        tmp = ""
        if self._isopen:
            for key in self._config['LINEOSDPOS']:
                if "line" == key.split('_')[0]:  # key is line_0 ... line_n from config file
                    val = literal_eval(self._config.get('LINEOSDPOS', key)) # val is key's val
                    tmp = 'pos_' + key.split('_')[1] # pos_0  pos_1 .... pos_n
                    posorder[key] = val
                else:
                    pass
                    
                if "pos" in tmp  and "endmask" in key:
                    dictpos[tmp] = posorder.copy()
                    posorder.clear()   
            return dictpos

# 界面显示元素
class DisplayDataOnScreen():
    def __init__(self):
        self._zoom_rate = 1.6
    def set_osd_lines(self, xycoordpair):
        self._line_pair = xycoordpair
        self._line_num = len(self._line_pair)
    
    def draw_osd_line(self, sourceid, display_meta):
        xy_coord = self.get_line_coord(sourceid)
        display_meta.num_lines = 1
        py_nvosd_line_params = display_meta.line_params[0]
        py_nvosd_line_params.x1 = xy_coord[0][0]
        py_nvosd_line_params.y1 = xy_coord[0][1]
        py_nvosd_line_params.x2 = xy_coord[1][0]
        py_nvosd_line_params.y2 = xy_coord[1][1]
        py_nvosd_line_params.line_width = 5
        py_nvosd_line_params.line_color.set(0.0, 1.0, 0.0, 1.0)
        return display_meta
    
    def get_line_coord(self, index):
        tmp = "pos_" + str(index)
        return self._line_pair[tmp]['line_' + str(index)]
    
    def set_osd_text_property(self, x_offset, y_offset, py_nvosd_text_params):
        py_nvosd_text_params.x_offset = x_offset
        py_nvosd_text_params.y_offset = y_offset
        py_nvosd_text_params.font_params.font_name = "Serif"
        py_nvosd_text_params.font_params.font_size = 10
        # set(red, green, blue, alpha); set to White
        py_nvosd_text_params.font_params.font_color.set(1.0, 1.0, 1.0, 1.0)
        py_nvosd_text_params.set_bg_clr = 1
        # set(red, green, blue, alpha); set to Black
        py_nvosd_text_params.text_bg_clr.set(0.0, 0.0, 0.0, 1.0)

         
# 构建gst 
class MakeGst:
    fps_streams = {}
    number_sources = 0
    is_live = False
    line_pair = None
    sourceidlist = {}
    dsobj = DisplayDataOnScreen()
    logger = Logger().getlogger()
    
    def __init__(self, gst, urilist):
        self._gst = gst
        self._urilist = urilist
        self.logger.info("Creating Pipeline")
        self._pipeline = self._gst.Pipeline()
        if not self._pipeline:
            self.logger.error("Unable to create Pipeline")
        for i in range(0, len(self._urilist)):
            MakeGst.fps_streams["stream{0}".format(i)] = GETFPS(i)
            exec('MakeGst.sourceid_{} = {}'.format(i, MakeGst.sourceidlist))
            exec('MakeGst.upcount_{} = {}'.format(i, 0))
            exec('MakeGst.downcount_{} = {}'.format(i, 0))
           
        MakeGst.number_sources = len(self._urilist)
        self._streammux = self.make_element("nvstreammux", "stream-muxer")
        self.__init_sourceid()
        self.__create_uri_bin()

    def __init_sourceid(self):
        for item in self._urilist:
            self.sourceidlist[item] = ""
            
    def set_sourceid(self, sourceid):
        for key, _ in self.sourceidlist.items():
            if self.sourceidlist[key] != "":
                self.sourceidlist[key] = sourceid

    def get_gst(self):
        return self._gst
    
    def get_pipe_line(self):
        return self._pipeline
    
    def make_element(self, elename, aliselename):
        self.logger.info("Creating {}".format(elename))
        element = self._gst.ElementFactory.make(elename, aliselename)
        if not element:
            self.logger.error(" Unable to create {}".format(element))
        else:
            self._pipeline.add(element)
            return element
    
    def get_element(self, elementname):
        element = None
        element = self._pipeline.get_by_name(elementname)
        if element:
            return element
        return None
    
    def __create_uri_bin(self):
        for i in range(MakeGst.number_sources):
            self.logger.info("Creating source_bin {}".format(i))
            uri_name = self._urilist[i]
            if uri_name.find("rtsp://") == 0 :
                MakeGst.is_live = True
            source_bin = self.__create_source_bin(i, uri_name)
            if not source_bin:
                self.logger.error("Unable to create source bin")
            self._pipeline.add(source_bin)
            padname = "sink_%u" %i
            sinkpad = self._streammux.get_request_pad(padname) 
            if not sinkpad:
                self.logger.error("Unable to create sink pad bin")
            srcpad = source_bin.get_static_pad("src")
            if not srcpad:
                self.logger.error("Unable to create src pad bin")
            srcpad.link(sinkpad)

    def __create_source_bin(self, index, uri):
        bin_name = "source-bin-%02d" % index
        self.logger.info("Creating source bin:{}".format(bin_name))
        nbin = self._gst.Bin.new(bin_name)
        if not nbin:
            self.logger.error("Unable to create source bin")
        uri_decode_bin=self._gst.ElementFactory.make("uridecodebin", "uri-decode-bin")
        if not uri_decode_bin:
            self.logger.error("Unable to create uri decode bin")
        uri_decode_bin.set_property("uri",uri)
        uri_decode_bin.connect("pad-added", self.__cb_newpad,nbin)
        uri_decode_bin.connect("child-added", self.__decodebin_child_added,nbin)
        self._gst.Bin.add(nbin,uri_decode_bin)
        bin_pad=nbin.add_pad(self._gst.GhostPad.new_no_target("src", self._gst.PadDirection.SRC))
        if not bin_pad:
            self.logger.error(" Failed to add ghost pad in source bin")
            return None
        return nbin

    def __cb_newpad(self, decodebin, decoder_src_pad, data):
        self.logger.info("In cb_newpad")
        caps = decoder_src_pad.get_current_caps()
        gststruct = caps.get_structure(0)
        gstname = gststruct.get_name()
        source_bin = data
        features = caps.get_features(0)
        if(gstname.find("video") != -1):
            if features.contains("memory:NVMM"):
                # Get the source bin ghost pad
                bin_ghost_pad=source_bin.get_static_pad("src")
                if not bin_ghost_pad.set_target(decoder_src_pad):
                    self.logger.error("Failed to link decoder src pad to source bin ghost pad")
            else:
                self.logger.error("Error: Decodebin did not pick nvidia decoder plugin")

    def __decodebin_child_added(self, child_proxy, Object, name, user_data):
        self.logger.info("Decodebin child added {}".format(name))
        if(name.find("decodebin") != -1):
            Object.connect("child-added", self.__decodebin_child_added, user_data)
    
    def set_element_property(self, ele, key ,value):
        ele.set_property(key, value)

    def handel_encode(self, codec):
        # Make the encoder
        if codec == "H264":
            self.logger.info("Creating H264 Encoder")
            encoder = self.make_element("nvv4l2h264enc", "encoder")
        elif codec == "H265":
            self.logger.info("Creating H265 Encoder")
            encoder = self.make_element("nvv4l2h265enc", "encoder")
        if not encoder:
            self.logger.error("Unable to create encoder")
            
        encoder.set_property('bitrate', 4000000)
        if is_aarch64():
            self.set_element_property(encoder, 'preset-level', 1)
            self.set_element_property(encoder, 'insert-sps-pps', 1)
            self.set_element_property(encoder, 'bufapi-version', 1)
        # Make the payload-encode video into RTP packets
        if codec == "H264":
            self.logger.info("Creating H264 rtppay")
            rtppay = self.make_element("rtph264pay", "rtppay")
        elif codec == "H265":
            self.logger.info("Creating H265 rtppay")
            rtppay = self.make_element("rtph265pay", "rtppay")
        if not rtppay:
            self.logger.error("Unable to create rtppay")

    def set_tracker_param(self, config, tracker):
        for key in config['tracker']:
            if key == 'tracker-width' :
                tracker_width = config.getint('tracker', key)
                tracker.set_property('tracker-width', tracker_width)
            if key == 'tracker-height' :
                tracker_height = config.getint('tracker', key)
                tracker.set_property('tracker-height', tracker_height)
            if key == 'gpu-id' :
                tracker_gpu_id = config.getint('tracker', key)
                tracker.set_property('gpu_id', tracker_gpu_id)
            if key == 'll-lib-file' :
                tracker_ll_lib_file = config.get('tracker', key)
                tracker.set_property('ll-lib-file', tracker_ll_lib_file)
            if key == 'll-config-file' :
                tracker_ll_config_file = config.get('tracker', key)
                tracker.set_property('ll-config-file', tracker_ll_config_file)
            if key == 'enable-batch-process' :
                tracker_enable_batch_process = config.getint('tracker', key)
                tracker.set_property('enable_batch_process', tracker_enable_batch_process)
            if key == 'enable-past-frame' :
                tracker_enable_past_frame = config.getint('tracker', key)
                tracker.set_property('enable_past_frame', tracker_enable_past_frame)

    def link_element(self, linklist):
        for idx, item in enumerate(linklist):
            if item == linklist[-1]:
                break
            ele = self.get_element(item)
            #print("ele--------------------->", ele)
            ele.link(self.get_element(linklist[idx+1]))