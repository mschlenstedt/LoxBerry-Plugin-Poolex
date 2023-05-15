#!/bin/bash

# Vars
repo="mschlenstedt/mqtt-landroid-bridge"

# Calculate vars
repourl="https://github.com/$repo.git"
packageurl="https://raw.githubusercontent.com/$repo/master/package.json"
pluginname=$(perl -e 'use LoxBerry::System; print $lbpplugindir; exit;')
oldversion=$(jq -r '.version' $LBPDATA/$pluginname/mqtt-landroid-bridge/package.json)

# print out versions
if [[ $1 == "current" ]]; then
	echo -n $oldversion
	exit 0
fi
if [[ $1 == "available" ]]; then
	newversion=$(curl -s $packageurl | jq -r '.version')
	echo -n $newversion
	exit 0
fi


# Logging
. $LBHOMEDIR/libs/bashlib/loxberry_log.sh
PACKAGE=$pluginname
NAME=upgrade
LOGDIR=${LBPLOG}/${PACKAGE}
STDERR=1
LOGSTART "Landroid-NG upgrade started."

# Clone Repo
LOGINF "Cloning $repo..."
rm -rf $LBPDATA/$pluginname/mqtt-landroid-bridge
git clone $repourl $LBPDATA/$pluginname/mqtt-landroid-bridge 2>&1 | tee -a $FILENAME

# Symlink config
LOGINF "Symlinking config file..."
rm $LBPDATA/$pluginname/mqtt-landroid-bridge/config.json
ln -sv $LBPCONFIG/$pluginname/config.json $LBPDATA/$pluginname/mqtt-landroid-bridge/config.json 2>&1 | tee -a $FILENAME

# Install
LOGINF "Installing..."
cd $LBPDATA/$pluginname/mqtt-landroid-bridge
npm install 2>&1 | tee -a $FILENAME

# End
newversion=$(jq -r '.version' $LBPDATA/$pluginname/mqtt-landroid-bridge/package.json)
LOGOK "Upgrading Bridge from $oldversion to $newversion"
LOGEND "Upgrading Bridge from $oldversion to $newversion"
exit 0
