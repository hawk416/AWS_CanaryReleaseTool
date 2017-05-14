# AWS_CanaryReleaseTool

A simple toolset for a canary style release in AWS

## Introduction

This toolset is the result of a technical challenge. The challenge has the following requirements:
- Create an AWS environment for cannary releases
- Automate the canary release procedure
- Add a failsafe if the new application version does not meet performance criteria

## Solution

The solution is comprised of multiple parts:

### AWS Environment

The environment should be setup using a Route53 Weighted DNS. This should select from two ElasticLoadBalancers, stable and release respectivelly. 
Each load balancer should serve one AutoScalingGroup. Each autoscalling group should have two sets of alarms, once for scaling, typically triggering a scale event based on CPU usage.
The other set of alarms should be a tight latency alarm generated for the purpouse of monitoring and release. This alarms should trigger SNS messages that will be received down the line by our application.

For more information, check the diagram in documents/aws_env.xml . This can be imported in https://draw.io for editing/viewing.

Setup AWS environment as follows:
- Route53 Weighted DNS -> A) Stable ELB
					|---> B) Release ELB
- ELB Scaling Policies
- ASG/ELB alarms for release monitoring
- SNS topics for alarms

### Scripts

There are two things that are handled by bash scripts. First is the initial setup and start of the release, release_init.sh, which will update the ASG definition to use a new AMI and let our monitoring application know there is a new release.
The second script is for finalizing the release. What it does in essence is shutting down the stable ASG.

### Application

Supports and monitors canary release. Monitors latency alarm on the relevant ASG (e.g. release ASG). This is achieved by subsribing to SNS topics and listening for SNS http messages. Adjusts the Route53 Weighted DNS to reflect alarms.

## Requirements

Scripts:
- awscli
- jq

Application:
- Flask
- Boto

