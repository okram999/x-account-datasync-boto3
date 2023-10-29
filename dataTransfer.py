### Issued as-is ###

# Python3 script to set up the required IAM policy and roles for a cross account data transfer using AWS DataSync
# The script also create the target datasync location i.e. the cross account s3 bucket in this case. This cannot be done using the AWS console as
# of 10/27/2023.


##### Pre-requisites:
# Create the IAM roles that can be assumed via the "Source Account". Once done update the .env file for `role_arn_to_assume_in_destination_account` value. This role is used by the AWS STS service to generate a temp x-account role and attach the s3 bucket policy.
# update the `datasync_admin_role_arn` in the .env file. this is the role that will have access to DataSync service
# Update other values in the .env file the names are self explanatory.
#################

import boto3
import json
import os
import time
from botocore.config import Config

my_config = Config(region_name="us-east-1")


from dotenv import load_dotenv


policy_to_attach = [
    "arn:aws:iam::aws:policy/AWSDataSyncFullAccess",
    "arn:aws:iam::aws:policy/AWSDataSyncReadOnlyAccess",
]


# create the source data sync role
def create_iam_role():
    iam = boto3.client("iam")

    assume_role_policy_document = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "datasync.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    )
    try:
        response = iam.create_role(
            RoleName="boto3-datasync-xaccount-s3-role",
            AssumeRolePolicyDocument=assume_role_policy_document,
        )
        print(f"Role created: {response['Role']['RoleName']} ")
        return response["Role"]["RoleName"]
    except iam.exceptions.EntityAlreadyExistsException:
        print("Role already exists")
        return "boto3-datasync-xaccount-s3-role"


def attach_iam_policy(policy_arn, role_name):
    iam = boto3.client("iam")

    response = iam.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
    print(response)


def create_iam_policy():
    # Create IAM client
    iam = boto3.client("iam")

    # Create a policy
    my_managed_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": [
                    "s3:GetBucketLocation",
                    "s3:ListBucket",
                    "s3:ListBucketMultipartUploads",
                ],
                "Effect": "Allow",
                "Resource": "arn:aws:s3:::" + os.environ.get("TARGET_S3_NAME"),
            },
            {
                "Action": [
                    "s3:AbortMultipartUpload",
                    "s3:DeleteObject",
                    "s3:GetObject",
                    "s3:ListMultipartUploadParts",
                    "s3:PutObject",
                    "s3:GetObjectTagging",
                    "s3:PutObjectTagging",
                ],
                "Effect": "Allow",
                "Resource": "arn:aws:s3:::" + os.environ.get("TARGET_S3_NAME") + "/*",
            },
        ],
    }
    try:
        response = iam.create_policy(
            PolicyName="boto3-custom-policy-datasync-xacc-s3-transfr-policy",
            PolicyDocument=json.dumps(my_managed_policy),
        )
        return response["Policy"]["Arn"]
    except iam.exceptions.EntityAlreadyExistsException:
        print("Policy already exists")
        return (
            "arn:aws:iam::"
            + os.environ.get("SOURCE_ACC_NUMBER")
            + ":policy/boto3-custom-policy-datasync-xacc-s3-transfr-policy"
        )


# assume role into destination account and create the S3 bucket
def attach_s3_policy(assuming_role_arn):
    bucket_policy = {
        "Version": "2008-10-17",
        "Statement": [
            {
                "Sid": "DataSyncCreateS3LocationAndTaskAccess",
                "Effect": "Allow",
                "Principal": {
                    "AWS": "arn:aws:iam::"
                    + os.environ.get("SOURCE_ACC_NUMBER")
                    + ":role/boto3-datasync-xaccount-s3-role"
                },
                "Action": [
                    "s3:GetBucketLocation",
                    "s3:ListBucket",
                    "s3:ListBucketMultipartUploads",
                    "s3:AbortMultipartUpload",
                    "s3:DeleteObject",
                    "s3:GetObject",
                    "s3:ListMultipartUploadParts",
                    "s3:PutObject",
                    "s3:GetObjectTagging",
                    "s3:PutObjectTagging",
                ],
                "Resource": [
                    "arn:aws:s3:::" + os.environ.get("TARGET_S3_NAME"),
                    "arn:aws:s3:::" + os.environ.get("TARGET_S3_NAME") + "/*",
                ],
            },
            {
                "Sid": "DataSyncCreateS3Location",
                "Effect": "Allow",
                "Principal": {"AWS": os.environ.get("datasync_admin_role_arn")},
                "Action": "s3:ListBucket",
                "Resource": "arn:aws:s3:::" + os.environ.get("TARGET_S3_NAME"),
            },
        ],
    }
    bucket_policy = json.dumps(bucket_policy)
    client = boto3.client("sts")
    response = client.assume_role(
        RoleArn=assuming_role_arn,
        RoleSessionName="boto3-datasync-xacc-s3-bucket-creation-temp-session",
    )

    new_session = boto3.Session(
        aws_access_key_id=response["Credentials"]["AccessKeyId"],
        aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
        aws_session_token=response["Credentials"]["SessionToken"],
    )
    s3 = new_session.client("s3")
    s3.put_bucket_policy(Bucket=os.environ.get("TARGET_S3_NAME"), Policy=bucket_policy)
    print("Desctination S3 bucket policy set...")


# create the datasync location for the destination s3 bucket in the source account
def create_datasync_location_s3():
    datasync = boto3.client("datasync", config=my_config)
    response = datasync.create_location_s3(
        S3StorageClass="STANDARD",
        S3BucketArn="arn:aws:s3:::" + os.environ.get("TARGET_S3_NAME"),
        S3Config={
            "BucketAccessRoleArn": "arn:aws:iam::"
            + os.environ.get("SOURCE_ACC_NUMBER")
            + ":role/boto3-datasync-xaccount-s3-role"
        },
    )
    print(
        f'DataSync location with the Arn: {response["LocationArn"]} created with HTTPStatusCode: {response["ResponseMetadata"]["HTTPStatusCode"]}'
    )
    return response["LocationArn"]


# main function to create the iam role and attach the policy
def main():
    # loading env variables
    load_dotenv()

    # create IAM Policy
    custom_policy = create_iam_policy()
    policy_to_attach.append(custom_policy)

    # create IAM Role
    src_account_role = create_iam_role()

    # Attached AWS and Customer managed policies to the role
    for policy in policy_to_attach:
        attach_iam_policy(policy, src_account_role)

    # sleep for 10 secs to allow the iam role to be created and attached to the source account
    print("Sleeping 10 secs")
    time.sleep(10)
    print("Waking up....")

    # attach the s3 bucketpolicy to the role in the destination account
    role_to_assume = os.environ.get("role_arn_to_assume_in_destination_account")
    attach_s3_policy(role_to_assume)

    # create the datasync location for the destination s3 bucket in the source account
    datasync_location_arn = create_datasync_location_s3()


if __name__ == "__main__":
    main()
