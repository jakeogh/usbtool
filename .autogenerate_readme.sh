#!/bin/sh

usbtool find-device --help

usbtool find-device --baud-rate 921600 --command-hex 100253411003 --response-hex 065341

usbtool find-device --serial-number DA1ZDECW
