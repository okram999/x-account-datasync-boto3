
# Cross Account AWS DataSync using boto3 SDK


Python3 script to set up the required IAM policy and roles for a cross account data transfer using AWS DataSync. The script also create the target datasync location i.e. the cross account s3 bucket in this case. This cannot be done using the AWS console as of 10/27/2023.


### Pre-requisites:
- Create the IAM roles that can be assumed via the "Source Account" in the target account. Update the .env file for `role_arn_to_assume_in_destination_account` value. This role is used by the AWS STS service to generate a temp x-account role and attach the s3 bucket policy.
- Create and Update the `datasync_admin_role_arn` in the .env file. this is the role that will have access to DataSync service
- Update other values in the .env file the names are self explanatory.



### Execution of the script

- Install `pipenv` in the workstation. `pip3 install pipenv`
- Launch the virtual env: `pipenv shell`
- Install the required python packages: `pipenv install`
- Execute the script `python3 dataTransfer.py` 



#### NOTE:

- If you have to delete the a virtual env: `exit` and `pipenv --rm`
- `pipenv graph` if you want to check the installed packages
