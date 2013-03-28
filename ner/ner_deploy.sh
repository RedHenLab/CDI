#!/bin/bash

# Deploy ner module (tSegment.jar) to /usr/local/bin folder

src_dir='/home/csa/CAS2/Mingjie/tSegment/'
target_dir='/usr/local/bin/ner/'

echo Deploying ner...

cd ${src_dir}
cp tSegment.jar ${target_dir}
cp -r lib ${target_dir}

echo Done.