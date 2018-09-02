#!/usr/bin/python3
'''
Lightning Flashbox: Faces of Lightning
@author: Stadicus

Folder structure
+-- img         images for ui & photo templates
+-- photos      taken pictures
+-- slideshow   slideshow images
+-- tmp         temp files to be overwritten
|
+- flashbox.py  main program, started by systemd
'''
import time, datetime, os
import json, requests, tweepy
from picamera import PiCamera
from gpiozero import Button
import subprocess
from wand.image import Image

# CONFIG
amount = 250000                                         # fee in mSat
button = Button(21)                                     # physical pin 40 (button to ground)
slideshow = ['slideshow1', 'slideshow2', 'slideshow3']  # raw image files in subdir 'slideshow'

# URI to a running & connected c-lightning / lightning-charge node
# https://github.com/ElementsProject/lightning-charge/blob/master/README.md
charge_url = 'https://api-token:super-secret-secret@lightning-charge.domain.com:5001'


# MAIN ROUTINE to take the picture
# --------------------------------
def takePicture(basedir):
  # SCREEN: creating invoice
  showScreen(basedir, 'img/creating-invoice.raw')
  timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')

  ## Generate & display invoice QR code
  invoice = lightning_createInvoice(250000, 'Lightning Flashbox Tweet')

  callSubprocess('qrencode -s 5 -o '+basedir+'/tmp/qr.png ' + invoice['payreq'])
  with Image(filename=basedir+'/tmp/qr.png') as qr:
    qr.crop(4,10,301,298)
    with Image(filename=basedir+'/img/polaroid_bg_qr.png') as bg:
        bg.composite(qr, 12, 22)
        bg.save(filename=basedir+'/tmp/qr.png')
  callSubprocess('ffmpeg -y -vcodec png -i '+basedir+'/tmp/qr.png -vcodec rawvideo -f rawvideo -pix_fmt rgb565 '+basedir+'/tmp/qr.raw')
  
  # SCREEN: show invoice qr code
  showScreen(basedir, 'tmp/qr.raw')
  timer = 0
  
  # Wait 60s for payment or button push
  # alternative: use long-polling (GET /invoice/:id/wait?timeout=[sec]), 
  #              but then we cannot check the button
  while timer < 60:   
    timer += 1
    button.wait_for_press(timeout=2)

    # Button pushed, show node URI as QR code
    if button.is_pressed:
      # SCREEN: show node connection URI
      showScreen(basedir, 'img/open-channel-qr.raw')
      time.sleep(2)
      button.wait_for_press(timeout=30)
      time.sleep(2)
      # exit back to slidehow
      return 
  
    # Invoice paid?
    invoice_status = lightning_getInvoice(invoice['id'])
    if invoice_status['status'] == 'paid':
      # SCREEN: payment received
      showScreen(basedir, 'img/payment-received.raw')
      time.sleep(3)
      break
  
  if invoice_status['status'] != 'paid':
    # SCREEN: invoice expired
    showScreen(basedir, 'img/payment-failed.raw')
    time.sleep(5)
    return 
    

  # SCREEN: Smile for the Camera!
  showScreen(basedir, 'img/smile.raw')
  time.sleep(2)

  # take picture
  camera = PiCamera()
  picture_basename = basedir+'/photos/flashbox-'+timestamp
  camera.capture(picture_basename+'.jpg')
  camera.close()
  
  # SCREEN: Wait for the picture
  showScreen(basedir, 'img/wait-for-picture.raw')

  # process picture
  with Image(filename=picture_basename+'.jpg') as photo:
    photo.crop(114,0,605)
    
    with photo.clone() as screen:
      with Image(filename=basedir+'/img/polaroid_bg_screen.png') as bg:
        screen.resize(297,289)
        bg.composite(screen, 12, 22)
        bg.format = 'jpeg'
        bg.save(filename=basedir+'/tmp/photo-screen.jpg')
        
        # SCREEN: Show picture
        callSubprocess('ffmpeg -y -i '+basedir+'/tmp/photo-screen.jpg -vcodec rawvideo -f rawvideo -pix_fmt rgb565 '+basedir+'/tmp/photo.raw')
        showScreen(basedir, 'tmp/photo.raw')

    with Image(filename=basedir+'/img/polaroid_bg_twitter.png') as bg:
      bg.composite(photo, 19, 36)
      bg.format = 'jpeg'
      bg.save(filename=basedir+'/tmp/photo-twitter.jpg')  
      bg.save(filename=picture_basename+'-twitter.jpg')

  # Tweet picture
  with open(basedir+'/twitter_auth.json') as file:
    secrets = json.load(file)

    auth = tweepy.OAuthHandler(secrets['consumer_key'], secrets['consumer_secret'])
    auth.set_access_token(secrets['access_token'], secrets['access_token_secret'])
    twitter = tweepy.API(auth)
    twitter.update_with_media(basedir+'/tmp/photo-twitter.jpg', '') 
    time.sleep(7)
    showScreen(basedir, 'img/check-twitter.raw')
    time.sleep(4)


def callSubprocess(cmd):
  subprocess.call(cmd.split())


def showScreen(basedir, img):
  callSubprocess('dd if='+basedir+'/'+img+' of=/dev/fb1 bs=307200 count=1')


def lightning_createInvoice(amount, description):
  invoice_details = {"msatoshi": amount, "description": "{}".format(description) }
  print(invoice_details)
  resp = requests.post(charge_url+'/invoice/', json=invoice_details)
  print(resp.json())
  return resp.json()


def lightning_getInvoice(id):
  resp = requests.get(charge_url+'/invoice/'+id)
  print(resp.json())
  return resp.json()


# INIT
basedir = os.path.dirname(os.path.realpath(__file__))

showScreen(basedir, 'img/startup.raw')
time.sleep(3)

# Start slideshow until button push
slidenum = 0
while True:
  # SCREEN: slideshow
  showScreen(basedir, 'slideshow/'+slideshow[slidenum]+'.raw')
  button.wait_for_press(timeout=15)

  if slidenum < len(slideshow)-1: 
    slidenum += 1
  else:  
    slidenum = 0

  if button.is_pressed:
    takePicture(basedir)