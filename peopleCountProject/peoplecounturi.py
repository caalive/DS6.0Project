#!/usr/bin/env python3
import sys
import os
sys.path.append("..")
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
import configparser
import math
import pyds
from gi.repository import GObject, Gst, GstRtspServer
from ctypes import *
from util import * 
from common.bus_call import bus_call
from gstpipeline import ProjectConfig, MakeGst
from logger import Logger

# 多种类识别
PROJECTCFGFILE = os.getcwd() + '/config.ini'
TRCRCFG = os.getcwd() + '/tracker/tracker_file_config.txt'
INFERCFG = os.getcwd() +'/pgie_config.txt'

# 自定义单种类识别（仅仅识别人）
#PROJECTCFGFILE = os.getcwd() + '/config.ini'
#TRCRCFG = os.getcwd() + '/tracker/tracker_file_configBak.txt'
#INFERCFG = os.getcwd() +'/pgie_configBak.txt'

def tiler_src_pad_buffer_probe(pad, info, u_data):
    frame_number = 0
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer")
        return
    
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    l_frame = batch_meta.frame_meta_list

    while l_frame is not None:
        try:
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
        except StopIteration:
            break
        
        currentTracker = eval("u_data.sourceid_{}".format(frame_meta.source_id))
        previousTracker = currentTracker.copy()
        currentTracker.clear()
        
        frame_number = frame_meta.frame_num  
        l_obj = frame_meta.obj_meta_list
        
        # objects sets in per frame
        while l_obj is not None:
            try:
                obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
                currentTracker[obj_meta.object_id] = get_center_coord(obj_meta.rect_params)
            except StopIteration:
                break
            try: 
                l_obj = l_obj.next
            except StopIteration:
                break
                   
        up_count = eval("u_data.upcount_{}".format(frame_meta.source_id))
        down_count = eval("u_data.downcount_{}".format(frame_meta.source_id))   
        up, down = compareCoords(previousTracker, currentTracker, u_data.dsobj.get_line_coord(frame_meta.source_id))
        exec("u_data.upcount_{} = {}".format(frame_meta.source_id, up_count + up))
        exec("u_data.downcount_{} = {}".format(frame_meta.source_id, down_count + down))
        up_count = eval("u_data.upcount_{}".format(frame_meta.source_id))
        down_count = eval("u_data.downcount_{}".format(frame_meta.source_id)) 
        
        try:
            l_frame = l_frame.next
        except StopIteration:
            break  
        
        display_meta = pyds.nvds_acquire_display_meta_from_pool(batch_meta)
        display_meta.num_labels = 2
        py_nvosd_text_params = display_meta.text_params[0]
        
        #--------------- draw dis info ------------------------
        py_nvosd_text_params.display_text = "Total: {} Up: {} Down: {}".format(up_count + down_count, up_count, down_count)
        u_data.dsobj.set_osd_text_property(30, 30, py_nvosd_text_params)

        #--------------- draw FPS -----------------------------
        py_nvosd_text_fps = display_meta.text_params[1]
        py_nvosd_text_fps.display_text = "FPS:{}".format(u_data.fps_streams["stream{0}".format(frame_meta.pad_index)].get_fps())
        u_data.dsobj.set_osd_text_property(30, 90, py_nvosd_text_fps)
       
        #---------------draw line-----------------------------
        u_data.dsobj.draw_osd_line(frame_meta.source_id, display_meta)
        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)
    
    if frame_number % 100 == 0:
        print("Frame Number=", frame_number) 
    return u_data.get_gst().PadProbeReturn.OK


def main():
    logger = Logger().getlogger()
    GObject.threads_init()
    Gst.init(None)
    logger.info("init GObject.threads_init success")
    
    # get project fcg
    cfg = ProjectConfig(PROJECTCFGFILE)
    urilist = cfg.get_uri()
    codec = cfg.get_codec()
    updsink_port_num = cfg.get_udp_port()
    rtsp_port_num = cfg.get_rtsp_port()
    tiled_size = cfg.get_tiled_size()
    
    # get tracker cfg
    trackercfg = configparser.ConfigParser()
    trackercfg.read(TRCRCFG)
    trackercfg.sections()
    
    mygst = MakeGst(Gst, urilist)
    mygst.dsobj.set_osd_lines(cfg.get_line_osd_pos())

    # make queue list
    queueList = ["queue" + str(item) for item in range(0, 10)]
    for i in range(0, 10):
        mygst.make_element("queue", "queue"+ str(i))
    

    mygst.make_element("nvinfer", "primary-inference")
    mygst.make_element("nvtracker", "tracker")
    mygst.make_element("nvmultistreamtiler", "nvtiler")
    
    tiler = mygst.get_element("nvtiler")
    tiler_rows=int(math.sqrt(mygst.number_sources))
    tiler_columns=int(math.ceil((1.0 * mygst.number_sources) / tiler_rows))
    mygst.set_element_property(tiler, "rows", tiler_rows)
    mygst.set_element_property(tiler, "columns", tiler_columns)
    mygst.set_element_property(tiler, "width", tiled_size[0])
    mygst.set_element_property(tiler, "height", tiled_size[1])
    
    mygst.make_element("nvvideoconvert", "convertor")
    mygst.make_element("nvvideoconvert", "convertor_postosd")
    caps = mygst.make_element("capsfilter", "filter")
    mygst.set_element_property(caps, "caps", mygst.get_gst().Caps.from_string("video/x-raw(memory:NVMM), format=I420"))
    mygst.handel_encode(codec)
    
    nvosd = mygst.make_element("nvdsosd", "onscreendisplay")
    mygst.set_element_property(nvosd, "process-mode", 0)
    mygst.set_element_property(nvosd, "display-text", 1)

    sink = mygst.make_element("udpsink", "udpsink")
    mygst.set_element_property(sink, 'host', '224.224.255.255')
    mygst.set_element_property(sink, 'port', updsink_port_num)
    mygst.set_element_property(sink, 'async', False)
    mygst.set_element_property(sink, 'sync', False)
    
    streammux = mygst.get_element("stream-muxer")
    if mygst.is_live:
        logger.info("Atleast one of the sources is live")
        mygst.set_element_property(streammux, "live-source", True)
    
    mygst.set_element_property(streammux, "width", 1280)
    mygst.set_element_property(streammux, "height", 720)
    mygst.set_element_property(streammux, "batch-size", mygst.number_sources)
    mygst.set_element_property(streammux, "batched-push-timeout", 4000000)
    
    pgie = mygst.get_element("primary-inference")
    mygst.set_element_property(pgie, "config-file-path",  INFERCFG)
    pgie_batch_size = pgie.get_property("batch-size")
    if(pgie_batch_size != mygst.number_sources):
        logger.warn("Overriding infer-config batch-size {} with number of sources {}".format(pgie_batch_size, mygst.number_sources))
        mygst.set_element_property(pgie, "batch-size",  mygst.number_sources)
    
    tracker = mygst.get_element("tracker")
    mygst.set_tracker_param(trackercfg, tracker)
    logger.info("Linking elements in mygst pipeline")
    # linkList = ["stream-muxer", "primary-inference", "tracker", 
    #             "nvtiler", "convertor", "onscreendisplay", "convertor_postosd", 
    #             "filter", "encoder", "rtppay", "udpsink"]

    linkList = ["stream-muxer", queueList[0], "primary-inference", queueList[1], "tracker", queueList[2],
                "nvtiler", queueList[3], "convertor", queueList[4], "onscreendisplay", queueList[5], 
                "convertor_postosd", queueList[6],"filter",queueList[7], "encoder", queueList[8], 
                "rtppay", queueList[9], "udpsink"]
    mygst.link_element(linkList)
    
    # create an event loop and feed gstreamer bus mesages to it
    pipeline = mygst.get_pipe_line()
    loop = GObject.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect ("message", bus_call, loop)
    
    tiler_src_pad = tracker.get_static_pad("src")
    if not tiler_src_pad:
        logger.error("Unable to get src pad")
        #sys.stderr.write(" Unable to get src pad \n")
    else:
        tiler_src_pad.add_probe(mygst.get_gst().PadProbeType.BUFFER, tiler_src_pad_buffer_probe, mygst)
        
    # List the sources
    logger.info("Now playing...")
    for i, source in enumerate(urilist):
        logger.info("URI source --> {}:{}".format(i + 1 , source))

    # Start streaming
    server = GstRtspServer.RTSPServer.new()
    server.props.service = "%d" % rtsp_port_num
    server.attach(None)
    factory = GstRtspServer.RTSPMediaFactory.new()
    factory.set_launch( "( udpsrc name=pay0 port=%d buffer-size=524288 caps=\"application/x-rtp, media=video, clock-rate=(int)90000, encoding-name=(string)%s, payload=96 \" )" % (updsink_port_num, codec))
    factory.set_shared(True)
    server.get_mount_points().add_factory("/out", factory)
    
    logger.info("DeepStream: Launched RTSP Streaming at rtsp://localhost:%d/out" % rtsp_port_num)
    logger.info("Starting pipeline")
    pipeline.set_state(mygst.get_gst().State.PLAYING)
    try:
        loop.run()
    except:
        pass
    # cleanup
    logger.info("Exiting app")
    pipeline.set_state(mygst.get_gst().State.NULL)

if __name__ == '__main__':
    sys.exit(main())
