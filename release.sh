#!/bin/bash
# release.sh
# BetVictor Technical task
# This is used to run the Auto Scaling Group update process
# and update the Weighted DNS to start using the new ASG

# GLOBAL
# Set this as required
HOSTED_ZONE_ID="my-hosted-zone"
ASG_NAME="asg-public-cannary"
DNSNAME="load-balancer-canary"
LAUNCHCONFIG_NAME = "cannary-config-01"
WEIGHT=100

# Update batch for DNS
CHANGE_BATCH=$(echo """
{
	"Comment": "New release, setting dns weight",
	"Changes": [
		{
		"Action" : "UPSERT"
		"ResourceRecordSet": {
			"Weight": $WEIGHT
			"AliasTarget": {
          		"DNSName": $DNSNAME,
			}
		}
	]
}
""")

# FUNCTIONS
# description: Increases the version number in the launch config name
# drguments: launcg config name
# return: String representing the new launch config name
function increase_version {
	return 0
}

# description: Strips unneccessary information from the LC
# arguments: Launch configuration obtained by the describe-launch-configuration call
# return: new launch configuration
function lc_strip {
	return 0
}

# description: Sets the new ami Id in the LC
# arguments: ami id and launch configuration
# return: launch configuration with new AMI id set
function set_new_ami {
	return 0
}

# MAIN
################
## ASG Update ##
################
# Get the current launch configuration
LAUNCHCONFIG = $(aws autoscaling describe-launch-configurations --launch-configuration-names $LAUNCHCONFIG_NAME)
# Returns:
#  {
#     "LaunchConfigurations": [
#         {
#             "UserData": null,
#             "EbsOptimized": false,
#             "LaunchConfigurationARN": "arn:aws:autoscaling:us-west-2:123456789012:launchConfiguration:98d3b196-4cf9-4e88-8ca1-8547c24ced8b:launchConfigurationName/my-launch-config",
#             "InstanceMonitoring": {
#                 "Enabled": true
#             },
#             "ImageId": "ami-043a5034",
#             "CreatedTime": "2014-05-07T17:39:28.599Z",
#             "BlockDeviceMappings": [],
#             "KeyName": null,
#             "SecurityGroups": [
#                 "sg-67ef0308"
#             ],
#             "LaunchConfigurationName": "my-launch-config",
#             "KernelId": null,
#             "RamdiskId": null,
#             "InstanceType": "t1.micro",
#             "AssociatePublicIpAddress": true
#         }
#     ]
# }
# Increase version
LAUNCHCONFIG_NAME=increase_version($LAUNCHCONFIG_NAME)
# Strip unnecessary from launch config
LAUNCHCONFIG=lc_strip($LAUNCHCONFIG)
# Get new launch config with ami corrected
LAUNCHCONFIG=set_new_ami($NEW_AMI, $LAUNCHCONFIG)
# Create the new launch config
LAUNCH_CONFIG_STATUS=$(aws autoscaling create-launch-configuration --launch-configuration-name $LAUNCHCONFIG_NAME)
# TODO:
# Handle status
# Update the ASG
ASG_STATUS=$(aws autoscaling update-auto-scaling-group --auto-scaling-group-name $ASG_NAME --launch-configuration-name $LAUNCHCONFIG_NAME)
# TODO:
# Handle status

################
## DNS Update ##
################
DNS_STATUS=$(aws route53 change-resource-record-sets --hosted-zone-id $HOSTED_ZONE_ID --change-batch $CHANGE_BATCH)

