# randoplayer

Plays random video content on a Raspberry Pi

## Requirements

* Raspberry Pi, SD Card, USB Storage, SD Card writer etc

## Setting up

1. Get Raspberry Pi Imager, choose a Raspberry Pi OS "Lite" version as we won't need a desktop environment.

2. Write it to the SD card, plug it in the Pi.

3. If you didn't customise the image use pi/pi to log in. In my script I used "sdplayer" as the user and it's what this readme/scripts expect.

4. Enable SSH via `raspi-config`.

##### USB drive setup

1. FAT32 format your USB device

2. Copy tv\_station.py to the root and then place series folders inside a "tv" folder. See "Folder Structure" for how to place content on it.

3. Insert a FAT32 formatted USB storage device now if you plan on using one, if not, skip to step 4.

4. Find your USB device by running lsblk

5. Run `sudo blkid` to get the UUID of the device

6. Edit `sudo nano /etc/fstab` to have `UUID=XXXX-XXXX /mnt/tvdrive vfat defaults,nofail,x-systemd.automount 0 2`

7. Make the mount point by running `sudo mkdir -p /mnt/tvdrive` and then running `sudo mount -a` to mount it.

##### Service Setup

1. `sudo apt update`

2. `sudo apt install python3-flask -y`

3. `sudo apt install vlc -y`

4. Set up the service by writing this file with these contents:\
   `sudo nano /etc/systemd/system/pitv.service`

```
[Unit]
Description=Pi TV Station
After=local-fs.target
RequiresMountsFor=/mnt/tvdrive

[Service]
User=sdplayer
ExecStart=/usr/bin/python3 /mnt/tvdrive/tv_station.py
WorkingDirectory=/home/sdplayer
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target

```

5. Enable and start the service:

```
sudo systemctl daemon-reexec
sudo systemctl enable pitv
sudo systemctl start pitv
```
Your pi should now start playing random episodes of stuff! - go to http\://\<your\_pi>:8080/ to see the playlist.

### Folder structure

The expected folder structure for media to live in is:

```
/mnt/tvdrive/                   # Mounted USB drive
└── tv/                         # Root folder for media content
    ├── ShowA/                  # Each subfolder is a "show"
    │   ├── episode1.mp4
    │   ├── episode2.avi
    │   └── episode3.mkv
    ├── ShowB/
    │   ├── ep01.mp4
    │   └── ep02.mp4
    └── ShowC/
        ├── part1.avi
        └── part2.mkv

```

### Troubleshooting

I had no audio over HDMI on my Raspberry Pi 1, so I had to run this to make ALSA use HDMI directly:

Run: `aplay -l`\
the output will look like:

```
**** List of PLAYBACK Hardware Devices **** 
card 0: Headphones [bcm2835 Headphones], device 0: bcm2835 Headphones [bcm2835 Headphones] 
Subdevices: 8/8 
Subdevice #0: 
subdevice #0 
...
Subdevice #7: 
subdevice #7 
card 1: vc4hdmi [vc4-hdmi], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0] 
Subdevices: 1/1 
Subdevice #0: subdevice #0
```

Based on that, edit this file to have the content below:

`sudo nano /etc/asound.conf`

```
defaults.pcm.card 1
defaults.pcm.device 0
defaults.ctl.card 1
```

`sudo reboot`
