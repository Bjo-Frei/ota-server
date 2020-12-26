#!/usr/bin/env python3

'''

 Copyright 2018 Sebastian Glahn
 Copyright 2020 Bjorn Freitag

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0
 
 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.

'''

import os
import argparse
import hashlib
import glob
import logging
import ssl
import http.server

FIRMWARE_DIRECTORY = os.environ['HOME'] + os.sep + "firmware"
FILENAME_UPDATEINFO = ".updateinfo"
SEND_SAMEVERSION = False

class HttpHandler(http.server.BaseHTTPRequestHandler):

    def getLatestFirmwareVersion(self, flavor, actual):
        result = "-1"
        for firmware in os.listdir(FIRMWARE_DIRECTORY):
            if firmware.startswith(flavor):
                test = firmware[firmware.rindex("-") +1:firmware.index('.bin')]
                if self.greaterVersion(actual,test) <= 0 and self.greaterVersion(test,result) > 0 and self.ValidFirmwareVersion(actual, test):
                    result = test
        return result

    def ValidFirmwareVersion(self, actual,version):
        if actual == version:
            return 1
        elif os.path.isfile(FIRMWARE_DIRECTORY + os.sep + FILENAME_UPDATEINFO):
            versionKey = "-1"
            versions = { line.split("=",1)[0] : line.split("=",2)[1] for line in open(FIRMWARE_DIRECTORY + os.sep + FILENAME_UPDATEINFO) }
            for key in versions:
                if self.greaterVersion(version, key) >= 0 and self.greaterVersion(versionKey, key) < 0:
                    versionKey = key
            if self.greaterVersion(version, versionKey) >= 0:
                result = self.greaterVersion(actual, versions[versionKey])
                return result >= 0
            return 1
        else:
            return 1

    def validRequest(self, flavor):
        return glob.glob(FIRMWARE_DIRECTORY + os.sep + flavor + '*') and (os.path.isfile(FIRMWARE_DIRECTORY + os.sep + flavor) or 'x-ESP8266-version' in self.headers)

    def greaterVersion(self, v1, v2):
        v1Array = [int(i) for i in v1.split(".")]
        v2Array = [int(i) for i in v2.split(".")]
        if len(v1Array) < len(v2Array):
            return self.greaterVersion(v2,v1)*-1
        else:
            result = 0
            for index in range(len(v1Array)):
                if index < len(v2Array):
                    if v2Array[index] < v1Array[index]:
                        result = 1
                    elif v2Array[index] > v1Array[index]:
                        result = -1
                else:
                    if 0 > v1Array[index]:
                        result = -1
                    elif 0 < v1Array[index]:
                        result = 1
                if result != 0:
                    break
            return result

    def buildHtmlResponse(self, status):
        self.send_response(status)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
       
    def buildStreamResponse(self, flavor, latest = ""):
        if len(latest) > 0:
            filename = flavor + '-' + latest + ".bin"     
        else:
            filename = flavor

        filepath = FIRMWARE_DIRECTORY + os.sep + filename
        self.send_response(200)
        self.send_header('Content-type', 'application/octet-stream')
        self.send_header('Content-Disposition', 'attachment; filename=' + filename)
        self.send_header('Content-Length', os.path.getsize(filepath))
        self.send_header('x-MD5', hashlib.md5(open(filepath, 'rb').read()).hexdigest())
        self.end_headers()
        with open(filepath, 'rb') as binary:
            self.wfile.write(binary.read())

    def do_GET(self):
        log_stat = { 'ip' : self.client_address[0] }
        logging.debug("Headers: " + ",".join("=".join(_) for _ in self.headers.items()),extra = log_stat)
        
        flavor = self.path.rsplit('/', 1)[-1]

        if flavor.startswith(FILENAME_UPDATEINFO):
            logging.error('Invalid request', extra = log_stat)
            self.buildHtmlResponse(400)
            return
        
        elif os.path.isfile(FIRMWARE_DIRECTORY + os.sep + flavor):
            logging.info('Sending firmware ' + flavor,extra = log_stat)
            self.buildStreamResponse(flavor)
            return
        
        if flavor.endswith(".bin"):
                flavor = flavor[:-4]
                
        if not self.validRequest(flavor):
            logging.error('Invalid request', extra = log_stat)
            self.buildHtmlResponse(400)
            return
        else:
            firmware_version = self.headers.get('x-ESP8266-version')
            latest = self.getLatestFirmwareVersion(flavor, firmware_version)
            
            if self.greaterVersion(firmware_version, latest) < 0 or (SEND_SAMEVERSION and self.greaterVersion(firmware_version, latest) == 0):
                logging.info('Sending firmware update for ' + flavor + ' from ' + firmware_version + ' to ' + latest + '.', extra = log_stat)
                self.buildStreamResponse(flavor, latest)
                return
            else:
                logging.debug('No update available', extra = log_stat)
                self.buildHtmlResponse(304)
                return


def parseArgs():
    parser = argparse.ArgumentParser(description='HTTP Server which delivers firmware binaries for Arduino OTA updates.')
    parser.add_argument('--dir', help='Directory containing the firmware binaries to serve. Default: ~/firmware', default=os.environ['HOME'] + os.sep + "firmware")
    parser.add_argument('--port', help='Server port. Default: 80.', default=80)
    parser.add_argument('--log', help='Log level. Default INFO', default='INFO')
    parser.add_argument('--cert', help='SSL cert file to enable HTTPS. Default empty=No HTTPS', default=None)
    parser.add_argument('--sameversion', help='Send same version again. Default: false', default=False)
    return parser.parse_args()

if __name__ == '__main__':
    args = parseArgs()

    if args.dir:
        FIRMWARE_DIRECTORY = args.dir

    if args.sameversion:
        SEND_SAMEVERSION = args.sameversion

    logging.basicConfig(format='%(asctime)-15s %(levelname)s %(ip)s --- %(message)s', level=args.log)

    try:
        server = http.server.HTTPServer(('', args.port), HttpHandler)
        if args.cert:
            server.socket = ssl.wrap_socket(server.socket, certfile=args.cert, server_side=True)

        print('Started httpserver on port ' + str(args.port) + ', firmware directory: ' + FIRMWARE_DIRECTORY)
        server.serve_forever()

    except KeyboardInterrupt:
        print('Shutting down httpserver')
        server.socket.close()
