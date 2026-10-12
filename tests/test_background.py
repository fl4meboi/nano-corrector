import numpy as np
import cv2
from nano_corrector.background import apply_background, fit_background
from nano_corrector import engine as E


def test_background_fit_reduces_wall_cast_and_keeps_saturated_subject():
    h,w=400,300
    lab=np.zeros((h,w,3),np.float32)
    lab[...,0]=91
    lab[...,1]=np.linspace(1,3,w)
    lab[...,2]=2
    rgb=np.rint(cv2.cvtColor(lab,cv2.COLOR_Lab2RGB)*255).astype(np.uint8)
    rgb[100:350,100:200]=[170,20,25]
    anchor,coeff,_=fit_background(rgb)
    out,clipped=apply_background(rgb,anchor.lab,coeff,np.array([92,.15,.6]))
    after=cv2.cvtColor(out.astype(np.float32)/255,cv2.COLOR_RGB2Lab)
    assert np.abs(np.median(after[:80,:,:],axis=(0,1))-np.array([92,.15,.6])).max()<.5
    assert np.array_equal(out[100:350,100:200],rgb[100:350,100:200])
    assert clipped==0


def test_bright_white_is_not_clipped_by_lightness_match():
    rgb=np.full((200,200,3),255,np.uint8)
    rgb[:100]=[228,225,224]
    out,clipped=apply_background(rgb,np.array([90,1,1]),np.array([[1,0,0,0,0,0],[1,0,0,0,0,0]]),np.array([92,.15,.6]))
    assert np.array_equal(out[100:],rgb[100:])
    assert clipped==0
