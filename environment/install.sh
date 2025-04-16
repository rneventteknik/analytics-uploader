#!/bin/bash

# Install dependencies
if ! [ -f "$(which pip3)" ] ; then
	apt install python3-pip
fi

# Install analytics-upload with pip3
pip3 install --break-system-packages analytics-uploader

# Stop any existing services
echo "Stopping old services..."
systemctl stop rn.analytics-uploader.service
systemctl stop rn.analytics-uploader.timer

# Remove old files
echo "Removing old files..."
rm -v /lib/systemd/system/rn.analytics-uploader.service
rm -v /lib/systemd/system/rn.analytics-uploader.timer

# Copy files
echo "Copying files..."
cp -v rn.analytics-uploader.service /lib/systemd/system/
cp -v rn.analytics-uploader.timer /lib/systemd/system/

# Reload SystemD files
echo "Reloading daemon definitions..."
systemctl daemon-reload

# Enable, restart and print status of services
echo "Starting service..."
systemctl enable rn.analytics-uploader.service
systemctl start rn.analytics-uploader.service
systemctl status rn.analytics-uploader.service

echo "Starting timer..."
systemctl enable rn.analytics-uploader.timer
systemctl start rn.analytics-uploader.timer
systemctl status rn.analytics-uploader.timer

# Albert
echo "🫖 I am a teapot. 🫖"
