#!/usr/bin/perl

# Copyright 2023 Michael Schlenstedt, michael@loxberry.de
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


##########################################################################
# Modules
##########################################################################

# use Config::Simple '-strict';
# use CGI::Carp qw(fatalsToBrowser);
use CGI;
use LoxBerry::System;
use LoxBerry::IO;
use Net::MQTT::Simple;
use LoxBerry::JSON;
use LoxBerry::Log;
use Scalar::Util qw(looks_like_number);
use warnings;
use strict;
#use Data::Dumper;

##########################################################################
# Variables
##########################################################################

my $log;
my $error;
my $response;
my $responseraw;
my $mqtt;
my $topic;

# Read Form
my $cgi = CGI->new;
my $q = $cgi->Vars;

my $version = LoxBerry::System::pluginversion();
my $template;

# Language Phrases
my %L;

## Logging for ajax requests
$log = LoxBerry::Log->new (
	name => 'SendCommand',
	filename => "$lbplogdir/sendcommand.log",
	stderr => 1,
	loglevel => 7,
	addtime => 1,
	append => 1,
	nosession => 1,
);

LOGSTART "SendCommand";

# Check what to do
if( !defined $q->{do} || !defined $q->{serial} ) {
	$error = "Parameters do and/or serial not defined";
}
elsif( $q->{do} eq "start" ) {
	&mqttconnect();
	my $command = '{"cmd":1}';
	$response = &mqttpublish($command);
}
elsif( $q->{do} eq "pause" ) {
	&mqttconnect();
	my $command = '{"cmd":2}';
	$response = &mqttpublish($command);
}
elsif( $q->{do} eq "stop" ) {
	&mqttconnect();
	my $command = '{"cmd":3}';
	$response = &mqttpublish($command);
}
elsif( $q->{do} eq "set_lock" ) {
	&mqttconnect();
	my $command = '{"cmd":5}';
	$response = &mqttpublish($command);
}
elsif( $q->{do} eq "set_unlock" ) {
	&mqttconnect();
	my $command = '{"cmd":6}';
	$response = &mqttpublish($command);
}
elsif( $q->{do} eq "set_reboot" ) {
	&mqttconnect();
	my $command = '{"cmd":7}';
	$response = &mqttpublish($command);
}
elsif( $q->{do} eq "set_areacfg" ) {
	my @values = split /,/, $q->{value};
	my $i = 0;
	foreach ( @values ) {
		$i++;
		if ( !looks_like_number($_) || $_ < 0 || $_ > 500  ) {
			$error = "Parameter value not defined or not a number or range not valid";
		}
	}
	if ($i ne 4) {
		$error = "Parameter value not defined or not a number or range not valid";
	}
	if ($error eq "") {
		&mqttconnect();
		my $command = '{"mz": [ ' . $q->{value} . ' ]}';
		$response = &mqttpublish($command);
	}
}
elsif( $q->{do} eq "set_startsequences" ) {
	my @values = split /,/, $q->{value};
	my $i = 0;
	foreach ( @values ) {
		$i++;
		if ( !looks_like_number($_) || $_ < 0 || $_ > 3  ) {
			$error = "Parameter value not defined or not a number or range not valid";
		}
	}
	if ($i ne 10) {
		$error = "Parameter value not defined or not a number or range not valid";
	}
	if ($error eq "") {
		&mqttconnect();
		my $command = '{"mzv": [ ' . $q->{value} . ' ]}';
		$response = &mqttpublish($command);
	}
}
elsif( $q->{do} eq "set_partymode" ) {
	if ( !defined $q->{value} || !looks_like_number($q->{value}) || $q->{value} < 0 || $q->{value} > 2  ) {
		$error = "Parameter value not defined or not a number or range not valid";
	} else {
		&mqttconnect();
		$q->{value} = $q->{value} * 1; # Convert to numeric
		my $command = '{"sc": { "m":' . $q->{value} . '}}';
		$response = &mqttpublish($command);
	}
}
elsif( $q->{do} eq "set_partymodetime" ) {
	if ( !defined $q->{value} || !looks_like_number($q->{value}) || $q->{value} < 0 || $q->{value} > 1440  ) {
		$error = "Parameter value not defined or not a number or range not valid";
	} else {
		&mqttconnect();
		$q->{value} = $q->{value} * 1; # Convert to numeric
		my $command = '{"sc": { "distm":' . $q->{value} . '}}';
		$response = &mqttpublish($command);
	}
}
elsif( $q->{do} eq "set_raindelay" ) {
	if ( !defined $q->{value} || !looks_like_number($q->{value}) || $q->{value} < 0 || $q->{value} > 300  ) {
		$error = "Parameter value not defined or not a number or range not valid";
	} else {
		&mqttconnect();
		$q->{value} = $q->{value} * 1; # Convert to numeric
		my $command = '{"rd":' . $q->{value} . '}';
		$response = &mqttpublish($command);
	}
}
elsif( $q->{do} eq "get_status" ) {
	my $statusfile = "/dev/shm/mqttfinder.json";
	my $statusjsonobj = LoxBerry::JSON->new();
	my $status = $statusjsonobj->open(filename => $statusfile);
	if (-e "/dev/shm/mqttfinder.json") {
		my $cfgfile = $lbpconfigdir . "/config.json";
		my $jsonobj = LoxBerry::JSON->new();
		my $cfg = $jsonobj->open(filename => $cfgfile);
		$topic = $cfg->{'mower'}[0]->{'topic'};
		$topic = "landroid" if (!$topic);
		$responseraw = $status->{'incoming'}->{$topic . "/" . $q->{serial} . "/mowerdata"}->{'p'};
	}
	if (!$responseraw) {
		$error = "Could not read MQTT finder data. Available from LoxBerry 3.0 on.";
	}
}

#####################################
# Manage Response and error
#####################################

if( (defined $response || defined $responseraw) and !defined $error ) {
	print "Status: 200 OK\r\n";
	print "Content-type: application/json; charset=utf-8\r\n\r\n";
	print to_json( { message => $response } ) if ($response);
	print $responseraw if ($responseraw);
	LOGOK "Parameters ok - responding with HTTP 200";
}
elsif ( defined $error and $error ne "" ) {
	print "Status: 500 Internal Server Error\r\n";
	print "Content-type: application/json; charset=utf-8\r\n\r\n";
	print to_json( { error => $error } );
	LOGCRIT "$error - responding with HTTP 500";
}
else {
	print "Status: 501 Not implemented\r\n";
	print "Content-type: application/json; charset=utf-8\r\n\r\n";
	$error = "Action ".$q->{action}." unknown";
	LOGCRIT "Method not implemented - responding with HTTP 501";
	print to_json( { error => $error } );
}

exit;


#####################################
# Manage MQTT
#####################################
sub mqttconnect
{

	$ENV{MQTT_SIMPLE_ALLOW_INSECURE_LOGIN} = 1;

	# From LoxBerry 3.0 on, we have MQTT onboard
	my $mqttcred = LoxBerry::IO::mqtt_connectiondetails();
	my $mqtt_username = $mqttcred->{brokeruser};
	my $mqtt_password = $mqttcred->{brokerpass};
	my $mqttbroker = $mqttcred->{brokerhost};
	my $mqttport = $mqttcred->{brokerport};

	if (!$mqttbroker || !$mqttport) {
        	$error = "MQTT isn't configured completely";
		return();
	};
	LOGDEB "MQTT Settings: User: $mqtt_username; Pass: $mqtt_password; Broker: $mqttbroker; Port: $mqttport";

	# Connect
	eval {
		LOGINF "Connecting to MQTT Broker";
		$mqtt = Net::MQTT::Simple->new($mqttbroker . ":" . $mqttport);
		if( $mqtt_username and $mqtt_password ) {
			LOGDEB "MQTT Login with Username and Password: Sending $mqtt_username $mqtt_password";
			$mqtt->login($mqtt_username, $mqtt_password);
		}
	};
	if ($@ || !$mqtt) {
		my $error = $@ || 'Unknown failure';
        	$error = "An error occurred - $error";
		return();
	};

	return();

};

##
## Publush MQTT Topic
##
sub mqttpublish
{

	my ($command) = @_;
	my $resp;

	my $cfgfile = $lbpconfigdir . "/config.json";
	my $jsonobj = LoxBerry::JSON->new();
	my $cfg = $jsonobj->open(filename => $cfgfile);
	$topic = $cfg->{'mower'}[0]->{'topic'};
	$topic = "landroid" if (!$topic);

	# Publish
	eval {
		$mqtt->publish($topic . "/" . $q->{serial} . "/set/json" => "$command");
	};
	$resp = "Publishing " . $topic . "/" . $q->{serial} . "/set/json" . " " . $command;
	LOGINF $resp;

	return ($resp);

};


END {
	if($log) {
		LOGEND;
	}
}

