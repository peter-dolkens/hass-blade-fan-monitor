#!/bin/sh
# Renders assets/icon.svg into the Home Assistant brand images (needs rsvg-convert).
set -e
cd "$(dirname "$0")"
out=../custom_components/blade_fan/brand
rsvg-convert -w 256 -h 256 icon.svg -o "$out/icon.png"
rsvg-convert -w 512 -h 512 icon.svg -o "$out/icon@2x.png"
