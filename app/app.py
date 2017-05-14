#!/usr/bin/python
#
# description:
#	Application that supports and monitors canary release.
#	Monitors latency alarm on the relevant ASG (e.g. release ASG).
#	Adjusts the Route53 Weighted DNS to reflect alarms. 
#
#	There should be two alarms setup:
#	1) Latency high - When the latency is above the treshold - send sns-msg: failure
#	2) Latency low - When latency is below treshold - sends sns-msg: success 
# 
#	This app receives HTTP messages for the release SNS Topic and
#	adjusts the Route53 Weighted DNS entries based on the message.
# 	Received: success: weight in favour of release
#	Received: failure: weight in favour of stable
#
#	Settings:
# 	Required setting:
# 	- endpoint: IP + Port of this app (default: localhost:5000)
# 	- aws_region : AWS Region
# 	- aws_arn : AWS User ARN 
# 	- aws_zone : AWS Route53 hosted zone name (default: example.com)
# 	- aws_record_type : record type (default: CNAME)
#	You can set the following settings:
#	- step: the step to use for adjusting weights. e.g. new_dns_weight=old_dns_weight+step. default(8)
#	- limit_upper: valid 0-255 - The upper limit of weight. If the dns weight of release equals or
#					exceeds this limit, the release is deemed success. (default: 240)
#	- limit_lower: valid 0-255 - The lower limit of weight. If the dns weight or release equals or is
#					lower then this limit, the release is deemed a failure and dns is
#					reverted back to stable. (default: 32)
#
# Primary endpoints:
#	/sns-topic:
#		- Used to receive SNS Topic notifications
#		- Receives either success or failure of cloudwatch alarm
#		- Sets the DNS weights in Route53 towards either stable or release LB
# 		- Takes JSON argument: 
#			{
#			   "Type" : "Notification",
#			   "MessageId" : "22b80b92-fdea-4c2c-8f9d-bdfb0c7bf324",
#			   "TopicArn" : "arn:aws:sns:us-west-2:123456789012:MyTopic",
#			   "Subject" : "SNS-TOPIC",
#			   "Message" : "SUCCESS | ERROR",
#			   "Timestamp" : "2012-05-02T00:54:06.655Z",
#			   "SignatureVersion" : "1",
#			   "Signature" : "EXAMPLEw6JRNwm1LFQL4ICB0bnXrdB8ClRMTQFGBqwLpGbM78tJ4etTwC5zU7O3tS6tGpey3ejedNdOJ+1fkIp9F2/LmNVKb5aFlYq+9rk9ZiPph5YlLmWsDcyC5T+Sy9/umic5S0UQc2PEtgdpVBahwNOdMW4JPwk0kAJJztnc=",
#			   "SigningCertURL" : "https://sns.us-west-2.amazonaws.com/SimpleNotificationService-f3ecfb7224c7233fe7bb5f59f96de52f.pem",
#			   "UnsubscribeURL" : "https://sns.us-west-2.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:us-west-2:123456789012:MyTopic:c9135db0-26c4-47ec-8998-413945fb5a96"
#		   }
#
#
#	/release:
#		- Used by admins to initiate the release
#		- Takes JSON Argument:
#			{
#				"dns_stable"="DNS name of release environment ELB"
#				"dns_release"="DNS name of release environment ELB"
#				"sns_stable"="SNS topic of stable environment"
#				"sns_release"="SNS topic of stable environment"
#			}
# Additional Endpoints:
#	/query:
#		- Used by admins to check on the status of release
#		- No input arguments
#		- returns:
#			{
#				"status":"in_progress|stable_operation",
#				"weight_stable":"",
#				"weight_release":""
#			}
#
#	/cancel:
#		- Cancels current release cycle
#		- Will set weights to stable
#
# ###############################################
# Amazon SNS message header:
# POST / HTTP/1.1
# x-amz-sns-message-type: Notification
# x-amz-sns-message-id: 22b80b92-fdea-4c2c-8f9d-bdfb0c7bf324
# x-amz-sns-topic-arn: arn:aws:sns:us-west-2:123456789012:MyTopic
# x-amz-sns-subscription-arn: arn:aws:sns:us-west-2:123456789012:MyTopic:c9135db0-26c4-47ec-8998-413945fb5a96
# Content-Length: 773
# Content-Type: text/plain; charset=UTF-8
# Host: example.com
# Connection: Keep-Alive
# User-Agent: Amazon Simple Notification Service Agent
#
#
#
##########
# IMPORT #
##########
import boto.sns, boto.route53
import json
from flask import Flask, request, jsonify

########
# USER #
########
# TODO:
# Get this from environment
ACCESS = '<REPLACE_WITH_ACCESS_KEY_ID>'
SECRET = '<REPLACE_WITH_SECRET_ACCESS_KEY>'
config={"limit_upper": 240,
		"limit_lower": 32,
		"step": 8,
		"endpoint": "localhost:5000",
		"aws_region":"eu-west-1",
		"aws_arn":"arn::",
		"aws_zone":"example.com",
		"aws_record_type":"CNAME",
		"dns_stable":"https://",
		"dns_release": "https://",
		"sns_stable": "",
		"sns_release": "",
		"sns_subscription":"",
		"in_progress": True
		}

############
# USER END #
############

#Init Flask
app = Flask(__name__)
# Init Boto SNS
# TODO: Add error handling
ROUTE53 = boto.route53.connect_to_region(config["aws_region"])
SNS=boto.sns.connect_to_region(config["aws_region"])
# TODO: get arn if none is set
# config[aws_arn]=boto.connect_iam().get_user().arn.split(':')[4]

# GLOBAL
# STATIC
# For testing purposes
APP_DEBUG=True

# FUNCTIONS
# description: 
# arguments:
# return

# description: Subscribes this applications /sns-topic endpoint
#				to SNS topic
# arguments: sns_name - name of the topic to subscribe
# return: True/False if subscription success
def sns_subscribe(sns_name):
	arn=":".join(["arn", "aws", "sns", config["aws_region"], config["aws_arn"], sns_name])
	# subsribe to topic
	# TODO: add some checks to verify subscribe wen't successfull
	sub = SNS.subscribe(arn, "http", config["aws_endpoint"]+"/sns-topic")
	# TODO: Add return
	return True

# description: unsubscribes the application endpoint from SNS
# arguments: sns_sub - SNS Subscription object
# return: True/False depending if success or failure
def sns_unsubscribe():
	# TODO: Check if unsubscribe is successfull
	SNS.unsubscribe(config["sns_subscription"])
	# TODO: Add return
	return True

# description: Used to confirm the subscription
# arguments:
# return: True/False depending if success or failure
def sns_confirm_subscription(topic,token):
	SNS.confirm_subscription(topic, token)
	return True

# description: Set's the weight of the given elb
# arguments: dns_name - dns name of the elb
#			 weight - weight
# return: True/False
def route53_set_weight(dns_name, weight):
	zone = ROUTE53.get_zone(config["aws_zone"])
	change_set = ResourceRecordSets(CONN, zone.id)
	changes = change_set.add_change("UPSERT", "www" + dns_name, type=config["aws_record_type"], weight=weight)
	change_set.commit()
	# TODO: Check response
	return True

# description: Returns the weight of the given elb
# arguments: dns_name - dns_name of the elb
# return: int - weight
def route53_get_weight(dns_name):
	zone = ROUTE53.get_zone(config["aws_zone"])
	record = zone.findrecords(dns_name, config["aws_record_type"], desired=1)
	# TODO: Extract only the integer
	weight = record.WRRBody 
	return weight

# description: Adjusts the weight of the given elb by increment
# arguments: dns_name - dns name of the elb
#			 increment - amount to be added/substracted if the amount is negative.
# return: True/False
def route53_adjust_weight(dns_name, increment):
	current_weight=route53_get_weight(dns_name)
	current_weight=(current_weight + increment)
	if current_weight > 255:
		current_weight=255
	elif current_weight < 0:
		current_weight=0
	result=route53_set_weight(dns_name, current_weight)
	return result

# description: wrapper for print that adds a timestamp
# arguments: msg - the message to be printed
def system_output(msg):
	print "%s %s" % (str(datetime.datetime.now()), msg)

# description: 
# arguments:
# return
def release_revert():
	return True

# description: Cancels the current release 
# arguments:msg - message to be returned
# return: JSON object/error message
def release_cancel(msg):
	# global IN_PROGESS config
	config["in_progress"]=False
	# config["dns_stable"]="https://"
	# config["dns_release"]="https://"
	return jsonify('{"status":"error", "message": "%s"' % msg )

# description: Processes requests for new release
# arguments: stable - dns of stable elb
#			 release - dns of release elb
# return: JSON-object:
# Success if the release is initiated
# Error otherwise
@app.route('/release')
def release():
	# global IN_PROGESS config
	# Check if already in progress
	if config["in_progress"]:
		return release_cancel("Release already in progress. Try the /query endpoint for more information")
	config["in_progress"]=True

	# Get the data
	msg=json.loads(request.json)
	# Check for fields
	if not msg["dns_stable"]:
		return release_cancel("Missing DNS information for stable environment: dns_stable")
	elif not msg["dns_release"]:
		return release_cancel("Missing DNS information for release environment: dns_release ")
	elif not msg["sns_stable"]:
		return release_cancel("Missing SNS information for stable environment: sns_stable ")
	elif not msg["sns_release"]:
		return release_cancel("Missing SNS information for release environment: sns_release ")

	# Set global
	config["dns_stable"]=msg["dns_stable"]
	config["dns_release"]=msg["dns_release"]
	config["sns_stable"]=msg["sns_stable"]
	config["sns_release"]=msg["sns_release"]

	# Subscribe to SNS Topic
	if not (sns_subscribe(config["sns_release"])):
		return release_cancel("Could not register to SNS Topic")
	# return success
	return jsonify('{"status": "success", "message": "Initiated new release"}')

# description: Processes SNS message 
# arguments: sns-message
# return: JSON
# {"status" : "ok"}
@app.route('/sns-topic')
def sns_process():
	# TODO: check for header
	msg=json.loads(request.json())
	# TODO: verify the sns
	# Check message and adjust state
	# TODO: Handle subscription
	if msg["Message"].startswith("success"):
		route53_adjust_weight(config["dns_release"], config["step"])
		route53_adjust_weight(config["dns_stable"], -config["step"])
	elif msg["Message"].startswith("failure"):
		route53_adjust_weight(config["dns_release"],-config["step"])
		route53_adjust_weight(config["dns_stable"], config["step"])
	else:
		# other type of message?
		return jsonify('{"status": "error", "message": "not in success/failure scenario"')

	# Check if weight is in upper/lower limits
	if route53_get_weight(config["dns_release"]) >= config["limit_upper"]:
		# Release is success
		sns_unsubscribe(config["sns_release"])		
		# Set the weights to fully route to release
		route53_set_weight(config["dns_release"], 255)
		route53_set_weight(config["dns_stable"], 0)
		# Msg admin to let him know to finalize the release
		msg_admin("Release application: Success", "Success in releasing to %s" % config["dns_release"])
		# Set in_progress flag
		config["in_progress"]=False
	elif route53_get_weight(config["dns_release"]) <= config["limit_lower"]:
		# Release failed
		sns_unsubscribe(config["sns_release"])
		# Set the weights to fully route to stable
		route53_set_weight(config["dns_stable"], 255)
		route53_set_weight(config["dns_release"], 0)
		# Msg admin 
		msg_admin("Release application: Error in release","Error in release, Reverting")
		# Set in_progress flag
		config["in_progress"]=False
	return jsonify('{"status": "ok"}')
	
# description: checks the current weights 
# arguments: none
# return: JSON Object:
# {
#	"status": "in_progress",
#	"weight_stable": <weight>,
#	"weight_release": <weight> 
# }
@app.route('/query')
def release_progress():
	if config["in_progress"]:
		return """{
				"status": "release_in_progress",
				"weight_stable": "%s",
				"weight_release": "%s"
		}""" % (route53_get_weight(config["dns_stable"]), route53_get_weight(config["dns_release"]))
	
	else:
		return """{
			"status": "stable_operation"
		}"""

# MAIN
if __name__ == '__main__':
  app.run(debug=APP_DEBUG)

# check message
# msg="""
# {
#   "Type" : "Notification",
#   "MessageId" : "22b80b92-fdea-4c2c-8f9d-bdfb0c7bf324",
#   "TopicArn" : "arn:aws:sns:us-west-2:123456789012:MyTopic",
#   "Subject" : "SNS-TOPIC",
#   "Message" : "RELEASE",
#   "Timestamp" : "2012-05-02T00:54:06.655Z",
#   "SignatureVersion" : "1",
#   "Signature" : "EXAMPLEw6JRNwm1LFQL4ICB0bnXrdB8ClRMTQFGBqwLpGbM78tJ4etTwC5zU7O3tS6tGpey3ejedNdOJ+1fkIp9F2/LmNVKb5aFlYq+9rk9ZiPph5YlLmWsDcyC5T+Sy9/umic5S0UQc2PEtgdpVBahwNOdMW4JPwk0kAJJztnc=",
#   "SigningCertURL" : "https://sns.us-west-2.amazonaws.com/SimpleNotificationService-f3ecfb7224c7233fe7bb5f59f96de52f.pem",
#   "UnsubscribeURL" : "https://sns.us-west-2.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:us-west-2:123456789012:MyTopic:c9135db0-26c4-47ec-8998-413945fb5a96"
#   }
# """
# msg=json.loads(msg)

# print msg
# if RELEASE
#	DNS set -step:+step
# elif ERROR
#	DNS set +step:-step

# endpoint release
#	- IN_PROGESS=True
#	- Set DNSDOMAIN_STABLE
#	- Set DNSDOMAIN_RELEASE
#	- Subscribe to Topic

# endpoint sns
#	- If error in release asg
#	- abort release | set more weight to stable
#