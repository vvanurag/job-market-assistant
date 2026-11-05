-- =============================================================================
-- Job Market Assistant: Snowflake foundation (Phase 0)
--
-- Creates the warehouse, database, Medallion schemas and three least-privilege
-- roles (NFR-12). Safe to re-run: every statement is idempotent.
--
-- Run in a Snowsight worksheet as a user holding SYSADMIN and SECURITYADMIN
-- (ACCOUNTADMIN on a trial account). Use "Run All" so every statement shares
-- one session. The three roles are granted to the user running the script.
-- =============================================================================

-- The user that will be granted all three roles: whoever runs this script.
-- current_user() returns the user object's exact name (which can differ from the
-- login name); the double quotes keep its exact case when used in identifier().
set dev_user = '"' || current_user() || '"';
select $dev_user as roles_will_be_granted_to, current_account() as account;

-- -----------------------------------------------------------------------------
-- 1. Compute and storage (owned by SYSADMIN)
-- -----------------------------------------------------------------------------
use role sysadmin;

create warehouse if not exists jma_wh
    warehouse_size = 'XSMALL'
    auto_suspend = 60                -- NFR-09: suspend after 60 s idle
    auto_resume = true
    initially_suspended = true
    comment = 'Job Market Assistant: all workloads (Phase 0)';

create database if not exists job_market
    comment = 'Job Market Assistant';

create schema if not exists job_market.bronze comment = 'Raw records as received (Medallion: Bronze)';
create schema if not exists job_market.silver comment = 'Cleaned, deduplicated, historised (Medallion: Silver)';
create schema if not exists job_market.gold   comment = 'Business-ready facts and dimensions (Medallion: Gold)';

-- Internal stage for loading raw files into Bronze
create stage if not exists job_market.bronze.raw_files
    comment = 'Landing area for raw JSON files before COPY INTO';

-- -----------------------------------------------------------------------------
-- 2. Roles (created by SECURITYADMIN, rolled up to SYSADMIN)
-- -----------------------------------------------------------------------------
use role securityadmin;

create role if not exists jma_ingest    comment = 'Writes raw data to Bronze';
create role if not exists jma_transform comment = 'Reads Bronze, builds Silver and Gold (dbt)';
create role if not exists jma_serve     comment = 'Read-only access to Gold for the API';

-- Role hierarchy: SYSADMIN can manage everything these roles create
grant role jma_ingest    to role sysadmin;
grant role jma_transform to role sysadmin;
grant role jma_serve     to role sysadmin;

-- -----------------------------------------------------------------------------
-- 3. Grants
-- -----------------------------------------------------------------------------

-- Warehouse: every role can run queries
grant usage, operate on warehouse jma_wh to role jma_ingest;
grant usage, operate on warehouse jma_wh to role jma_transform;
grant usage          on warehouse jma_wh to role jma_serve;

-- Database
grant usage on database job_market to role jma_ingest;
grant usage on database job_market to role jma_transform;
grant usage on database job_market to role jma_serve;

-- Ingest: create and load tables in Bronze only
grant usage, create table on schema job_market.bronze to role jma_ingest;
grant read, write on stage job_market.bronze.raw_files to role jma_ingest;

-- Transform: read Bronze; build Silver and Gold
grant usage on schema job_market.bronze to role jma_transform;
grant select on all tables    in schema job_market.bronze to role jma_transform;
grant select on future tables in schema job_market.bronze to role jma_transform;
grant usage, create table, create view on schema job_market.silver to role jma_transform;
grant usage, create table, create view on schema job_market.gold   to role jma_transform;

-- Serve: read Gold only (NFR-12, NFR-13)
grant usage on schema job_market.gold to role jma_serve;
grant select on all tables    in schema job_market.gold to role jma_serve;
grant select on future tables in schema job_market.gold to role jma_serve;
grant select on all views     in schema job_market.gold to role jma_serve;
grant select on future views  in schema job_market.gold to role jma_serve;

-- Development user gets all three roles; services will get one role each later
grant role jma_ingest    to user identifier($dev_user);
grant role jma_transform to user identifier($dev_user);
grant role jma_serve     to user identifier($dev_user);

-- -----------------------------------------------------------------------------
-- 4. Verify
-- -----------------------------------------------------------------------------
-- Expect exactly three rows: USAGE on JMA_WH, JOB_MARKET and JOB_MARKET.GOLD.
-- SELECT grants appear here only once Gold contains tables or views.
show grants to role jma_serve;

-- Expect SELECT on future TABLE and VIEW objects for JMA_SERVE (and none for other privileges).
show future grants in schema job_market.gold;
