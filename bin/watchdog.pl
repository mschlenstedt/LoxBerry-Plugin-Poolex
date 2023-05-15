#!/usr/bin/perl

use LoxBerry::System;
use LoxBerry::IO;
use LoxBerry::Log;
use LoxBerry::JSON;
use Getopt::Long;
#use warnings;
use strict;
#use Data::Dumper;

# Version of this script
my $version = "0.5.0";

# Globals
my $error;
my $verbose;
my $action;

# Logging
# Create a logging object
my $log = LoxBerry::Log->new (  name => "watchdog",
package => 'landroid-ng',
logdir => "$lbplogdir",
addtime => 1,
);
$log->default;

# Commandline options
# CGI doesn't work from other CGI skripts... :-(
GetOptions ('verbose=s' => \$verbose,
            'action=s' => \$action);

# Verbose
if ($verbose) {
        $log->stdout(1);
        $log->loglevel(7);
}

LOGSTART "Starting Watchdog";

# Lock
my $status = LoxBerry::System::lock(lockfile => 'landroid-ng-watchdog', wait => 120);
if ($status) {
    print "$status currently running - Quitting.";
    exit (1);
}

# Read Configuration
my $cfgfile = $lbpconfigdir . "/config.json";
my $jsonobj = LoxBerry::JSON->new();
my $cfg = $jsonobj->open(filename => $cfgfile);
if ( !%$cfg ) {
	LOGERR "Cannot open configuration $cfgfile. Exiting.";
	exit (1);
}

# Set Defaults from config

# Todo
if ( $action eq "start" ) {

	&start();

}

elsif ( $action eq "stop" ) {

	&stop();

}

elsif ( $action eq "restart" ) {

	&restart();

}

elsif ( $action eq "check" ) {

	&check();

}

else {

	LOGERR "No valid action specified. action=start|stop|restart|check is required. Exiting.";
	print "No valid action specified. action=start|stop|restart|check is required. Exiting.\n";
	exit(1);

}

#LOGEND "This is the end - My only friend, the end...";
#LoxBerry::System::unlock(lockfile => 'landroid-ng-watchdog');

exit;


#############################################################################
# Sub routines
#############################################################################

##
## Start
##
sub start
{

	if (-e  "$lbpconfigdir/bridge_stopped.cfg") {
		unlink("$lbpconfigdir/bridge_stopped.cfg");
	}

	# Save defaults
	my $mqttcred = LoxBerry::IO::mqtt_connectiondetails();
	my $cred;
	if ( $mqttcred->{brokeruser} && $mqttcred->{brokerpass} ) {
		$cred = "$mqttcred->{brokeruser}" . ":" . $mqttcred->{brokerpass} . "@";
	}
	my $mqtturl = "mqtt://" . $cred . $mqttcred->{brokeraddress};
	my $oldurl = $cfg->{'mqtt'}->{'url'};
	if ( $oldurl ne $mqtturl ) {
		$cfg->{'mqtt'}->{'url'} = $mqtturl;
		$jsonobj->write();
	}
	my $loglevel = $log->loglevel();
	my $nodejsloglevel = "debug";
	if ($loglevel > 6) {
		$nodejsloglevel = "debug";
	} elsif ( $loglevel > 5) {
		$nodejsloglevel = "info";
	} elsif ( $loglevel > 3) {
		$nodejsloglevel = "warn";
	} elsif ( $loglevel > 2) {
		$nodejsloglevel = "error";
	} else {
		$nodejsloglevel = "silent";
	}
	my $oldnodejsloglevel = $cfg->{'logLevel'};
	if ( $oldnodejsloglevel ne $nodejsloglevel ) {
		$cfg->{'logLevel'} = $nodejsloglevel;
		$jsonobj->write();
	}

	LOGINF "START called...";
	LOGINF "Starting Bridge...";
	# Logging for Bridge
	# Create a logging object
	my $logtwo = LoxBerry::Log->new (  name => "bridge",
	package => 'landroid-ng',
	logdir => "$lbplogdir",
	addtime => 1,
	);
	$logtwo->LOGSTART("Bridge started.");
	$logtwo->INF("Bridge will be started.");
	my $bridgelogfile = $logtwo->filename();
	system ("pkill -f mqtt-landroid-bridge/bridge.js");
	sleep 2;
	system ("node $lbpdatadir/mqtt-landroid-bridge/bridge.js >> $bridgelogfile 2>&1 &");

	LOGOK "Done.";

	return(0);

}

sub stop
{

	LOGINF "STOP called...";
	LOGINF "Stopping Bridge...";
	system ("pkill -f mqtt-landroid-bridge/bridge.js");

	my $response = LoxBerry::System::write_file("$lbpconfigdir/bridge_stopped.cfg", "1");

	LOGOK "Done.";

	return(0);

}

sub restart
{

	LOGINF "RESTART called...";
	&stop();
	sleep (2);
	&start();

	return(0);

}

sub check
{

	LOGINF "CHECK called...";

	if (-e  "$lbpconfigdir/bridge_stopped.cfg") {
		LOGOK "Bridge was stopped manually. Nothing to do.";
		return(0);
	}
	
	# Creating tmp file with failed checks
	if (!-e "/dev/shm/landroid-ng-watchdog-fails.dat") {
		my $response = LoxBerry::System::write_file("/dev/shm/landroid-ng-watchdog-fails.dat", "0");
	}

	my ($exitcode, $output)  = execute ("pgrep -f mqtt-landroid-bridge/bridge.js");
	if ($exitcode != 0) {
		LOGWARN "Bridge seems to be dead - Error $exitcode";
		my $fails = LoxBerry::System::read_file("/dev/shm/landroid-ng-watchdog-fails.dat");
		chomp ($fails);
		$fails++;
		my $response = LoxBerry::System::write_file("/dev/shm/landroid-ng-watchdog-fails.dat", "$fails");
		if ($fails > 9) {
			LOGERR "Too many failures. Will stop watchdogging... Check your configuration and start bridge manually.";
		} else {
			&restart();
		}
	} else {
		LOGOK "Bridge seems to be alive. Nothing to do.";
		my $response = LoxBerry::System::write_file("/dev/shm/landroid-ng-watchdog-fails.dat", "0");
	}

	return(0);

}

##
## Always execute when Script ends
##
END {

	LOGEND "This is the end - My only friend, the end...";
	LoxBerry::System::unlock(lockfile => 'landroid-ng-watchdog');

}
