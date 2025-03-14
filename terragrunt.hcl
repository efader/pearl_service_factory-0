# This is the configuration for Terragrunt, a thin wrapper for Terraform: https://terragrunt.gruntwork.io/

# Override the terraform source with the actual version we want to deploy.
terraform {
  source = "git@github.com:PearlHealth/infrastructure-modules.git//modules/services/app/saf-data-to-s3-export?ref=e4385f14a896d8fd22f68426b7c2e0f6b5df7c84"
}

# Include the root `terragrunt.hcl` configuration, which has settings common across all environments & components.
include "root" {
  path = find_in_parent_folders()
}

include "vpc" {
  path = find_in_parent_folders("vpc.hcl")
  # We want to reference the locals from this config, so we expose it.
  expose = true
}

# ---------------------------------------------------------------------------------------------------------------------
# Module parameters to pass in. Make sure to update these values for each environment.
# ---------------------------------------------------------------------------------------------------------------------
inputs = {
  environment                          = "prod"
  vpc_id                               = include.vpc.locals.app_vpc_id
  source_db_security_group_id          = "sg-098296a61fd32f6b1"
  replication_subnet_group_description = "Subnet ids for the production envionrment"
  replication_subnets                  = include.vpc.locals.app_private_subnet_ids
  source_db_username_password_arn      = "arn:aws:secretsmanager:us-east-2:902542500470:secret:peridot_dms_user_password_prod-T8Qehz"
  source_db_server_name                = "pearl-production.cruvwl7zthqz.us-east-2.rds.amazonaws.com"
}