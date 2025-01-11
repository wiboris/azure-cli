# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

import os
from azure.cli.core.util import get_file_json
from urllib.parse import urlsplit
from azure.batch.models import (DiskEncryptionTarget)

# TYPES VALIDATORS


def datetime_format(value):
    """Validate the correct format of a datetime string and deserialize."""
    from msrest.serialization import Deserializer
    from msrest.exceptions import DeserializationError
    try:
        datetime_obj = Deserializer.deserialize_iso(value)
    except DeserializationError:
        message = "Argument {} is not a valid ISO-8601 datetime format"
        raise ValueError(message.format(value))
    return datetime_obj


def disk_encryption_target_format(value):
    """Space seperated target disks to be encrypted. Values can either be OsDisk or TemporaryDisk"""
    if value.lower() == 'osdisk':
        return DiskEncryptionTarget.OS_DISK
    if value.lower() == 'temporarydisk':
        return DiskEncryptionTarget.TEMPORARY_DISK
    message = 'Argument {} is not a valid disk_encryption_target'
    raise ValueError(message.format(value))


def disk_encryption_configuration_format(value):
    targets = value.split(' ')
    parsed_targets = []
    for target in targets:
        parsed_targets.append(disk_encryption_target_format(target))
    return targets


def duration_format(value):
    """Validate the correct format of a timespan string and deserilize."""
    from msrest.serialization import Deserializer
    from msrest.exceptions import DeserializationError
    try:
        duration_obj = Deserializer.deserialize_duration(value)
    except DeserializationError:
        message = "Argument {} is not in a valid ISO-8601 duration format"
        raise ValueError(message.format(value))
    return duration_obj


def metadata_item_format(value):
    """Space-separated values in 'key=value' format."""
    try:
        data_name, data_value = value.split('=')
    except ValueError:
        message = ("Incorrectly formatted metadata. "
                   "Argument values should be in the format a=b c=d")
        raise ValueError(message)
    return {'name': data_name, 'value': data_value}


def string_dictionary_format(values):
    """Space-separated values in 'key=value' format."""
    if not values:
        raise ValueError("No values found. "
                         "Argument values should be in the format a=b c=d")
    result = {}
    try:
        for value in values.split(' '):
            k, v = value.split('=')
            result[k] = v
    except ValueError:
        message = ("Incorrectly formatted values. "
                   "Argument values should be in the format a=b c=d")
        raise ValueError(message)
    return result


def resource_tag_format(values):
    """Space-separated values in 'key=value' format."""
    if not values:
        raise ValueError("No values in resource tags. "
                         "Argument values should be in the format a=b c=d")
    result = {}
    try:
        for value in values.split(' '):
            k, v = value.split('=')
            result[k] = v
    except ValueError:
        message = ("Incorrectly formatted resource tags. "
                   "Argument values should be in the format a=b c=d")
        raise ValueError(message)
    return result


def environment_setting_format(value):
    """Space-separated values in 'key=value' format."""
    try:
        env_name, env_value = value.split('=')
    except ValueError:
        message = ("Incorrectly formatted environment settings. "
                   "Argument values should be in the format a=b c=d")
        raise ValueError(message)
    return {'name': env_name, 'value': env_value}


def batch_application_package_reference_format(value):
    """Space-separated application IDs with optional version in 'id[#version]' format."""
    app_reference = value.split('#', 1)
    package = {'applicationId': app_reference[0]}
    try:
        package['version'] = app_reference[1]
    except IndexError:  # No specified version - ignore
        pass
    return package


def batch_task_id_ranges_format(value):
    """Space-separated number ranges in 'start-end' format."""
    try:
        start, end = [int(i) for i in value.split('-')]
    except ValueError:
        message = ("Incorrectly formatted task ID range. "
                   "Argument values should be numbers in the format 'start-end'")
        raise ValueError(message)
    return {'start': start, 'end': end}


def resource_file_format(value):
    """Space-separated resource references in filename=httpurl format."""
    try:
        file_name, http_url = value.split('=', 1)
    except ValueError:
        message = ("Incorrectly formatted resource reference. "
                   "Argument values should be in the format filename=httpurl")
        raise ValueError(message)
    return {'file_path': file_name, 'http_url': http_url}


# COMMAND NAMESPACE VALIDATORS

def validate_required_parameter(namespace, parser):
    """Validates required parameters in Batch complex objects"""
    if not parser.done:
        parser.parse(namespace)


def storage_account_id(cmd, namespace):
    """Validate storage account name"""
    from azure.cli.core.profiles import ResourceType
    from azure.cli.core.commands.client_factory import get_mgmt_service_client

    if (namespace.storage_account and not
            ('/providers/Microsoft.ClassicStorage/storageAccounts/' in namespace.storage_account or
             '/providers/Microsoft.Storage/storageAccounts/' in namespace.storage_account)):
        storage_client = get_mgmt_service_client(cmd.cli_ctx, ResourceType.MGMT_STORAGE)
        acc = storage_client.storage_accounts.get_properties(namespace.resource_group_name,
                                                             namespace.storage_account)
        if not acc:
            raise ValueError(f"Storage account named '{namespace.storage_account}'" +
                             f" not found in the resource group '{namespace.resource_group_name}'.")
        namespace.storage_account = acc.id  # pylint: disable=no-member


def keyvault_id(cmd, namespace):
    """Validate storage account name"""
    from azure.cli.core.profiles import ResourceType
    from azure.cli.core.commands.client_factory import get_mgmt_service_client
    if not namespace.keyvault:
        return
    if '/providers/Microsoft.KeyVault/vaults/' in namespace.keyvault:
        resource = namespace.keyvault.split('/')
        kv_name = resource[resource.index('Microsoft.KeyVault') + 2]
        kv_rg = resource[resource.index('resourceGroups') + 1]
    else:
        kv_name = namespace.keyvault
        kv_rg = namespace.resource_group_name
    try:
        keyvault_client = get_mgmt_service_client(cmd.cli_ctx, ResourceType.MGMT_KEYVAULT)
        vault = keyvault_client.vaults.get(kv_rg, kv_name)
        if not vault:
            raise ValueError(f"KeyVault named '{kv_name}' not found in the resource group '{kv_rg}'.")
        namespace.keyvault = vault.id  # pylint: disable=no-member
        namespace.keyvault_url = vault.properties.vault_uri
    except Exception as exp:
        raise ValueError(f'Invalid KeyVault reference: {namespace.keyvault}\n{exp}')


def application_enabled(cmd, namespace):
    """Validates account has auto-storage enabled"""
    from azure.mgmt.batch import BatchManagementClient
    from azure.cli.core.commands.client_factory import get_mgmt_service_client

    client = get_mgmt_service_client(cmd.cli_ctx, BatchManagementClient)
    acc = client.batch_account.get(namespace.resource_group_name, namespace.account_name)
    if not acc:
        raise ValueError(f"Batch account '{namespace.account_name}' not found.")
    if not acc.auto_storage or not acc.auto_storage.storage_account_id:  # pylint: disable=no-member
        raise ValueError(f"Batch account '{namespace.account_name}' needs auto-storage enabled.")


def validate_pool_resize_parameters(namespace):
    """Validate pool resize parameters correct"""
    if not namespace.abort and not namespace.target_dedicated_nodes:
        raise ValueError("The target-dedicated-nodes parameter is required to resize the pool.")


def validate_json_file(namespace):
    """Validate the give json file existing"""
    if namespace.json_file:
        try:
            get_file_json(namespace.json_file)
        except OSError:
            raise ValueError("Cannot access JSON request file: " + namespace.json_file)
        except ValueError as err:
            raise ValueError(f"Invalid JSON file: {err}")


def validate_cert_file(namespace):
    """Validate the give cert file existing"""
    try:
        with open(namespace.certificate_file, "rb"):
            pass
    except OSError:
        raise ValueError("Cannot access certificate file: " + namespace.certificate_file)


def validate_options(namespace):
    """Validate any flattened request header option arguments."""
    try:
        start = namespace.start_range
        end = namespace.end_range
    except AttributeError:
        return
    namespace.ocp_range = None
    del namespace.start_range
    del namespace.end_range
    if start or end:
        start = start if start else 0
        end = end if end else ""
        namespace.ocp_range = f"bytes={start}-{end}"


def validate_file_destination(namespace):
    """Validate the destination path for a file download."""
    try:
        path = namespace.destination
    except AttributeError:
        return
    # TODO: Need to confirm this logic...
    file_path = path
    file_dir = os.path.dirname(path)
    if os.path.isdir(path):
        file_name = os.path.basename(namespace.file_name)
        file_path = os.path.join(path, file_name)
    elif not os.path.isdir(file_dir):
        try:
            os.mkdir(file_dir)
        except OSError as exp:
            message = "Directory {} does not exist, and cannot be created: {}"
            raise ValueError(message.format(file_dir, exp))
    if os.path.isfile(file_path):
        raise ValueError(f"File {file_path} already exists.")
    namespace.destination = file_path

# CUSTOM REQUEST VALIDATORS


def validate_pool_settings(namespace, _):
    """Custom parsing to enfore that either PaaS or IaaS instances are configured
    in the add pool request body.
    """
    if not namespace.json_file:
        if namespace.node_agent_sku_id and not namespace.image:
            raise ValueError("Missing required argument: --image")
        if namespace.image:
            try:
                namespace.publisher, namespace.offer, namespace.sku = namespace.image.split(':', 2)
                try:
                    namespace.sku, namespace.version = namespace.sku.split(':', 1)
                except ValueError:
                    pass
            except ValueError:
                if '/' not in namespace.image:
                    message = ("Incorrect format for VM image. Should be in the format: \n"
                               "'publisher:offer:sku[:version]' OR a URL to an ARM image.")
                    raise ValueError(message)

                namespace.virtual_machine_image_id = namespace.image
            del namespace.image
            if namespace.disk_encryption_targets:
                namespace.targets = namespace.disk_encryption_targets
                del namespace.disk_encryption_targets

        if namespace.auto_scale_formula:
            namespace.enable_auto_scale = True


def validate_cert_settings(namespace):
    """Custom parsing for certificate commands - adds default thumbprint
    algorithm.
    """
    namespace.thumbprint_algorithm = 'sha1'


def validate_client_parameters(cmd, namespace):
    """Retrieves Batch connection parameters from environment variables"""
    from azure.mgmt.batch import BatchManagementClient
    from azure.cli.core.commands.client_factory import get_mgmt_service_client

    # simply try to retrieve the remaining variables from environment variables
    if not namespace.account_name:
        namespace.account_name = cmd.cli_ctx.config.get('batch', 'account', None)
    if not namespace.account_key:
        namespace.account_key = cmd.cli_ctx.config.get('batch', 'access_key', None)
    if not namespace.account_endpoint:
        namespace.account_endpoint = cmd.cli_ctx.config.get('batch', 'endpoint', None)

    # Simple validation for account_endpoint
    if namespace.account_endpoint and not (namespace.account_endpoint.startswith('https://') or
                                           namespace.account_endpoint.startswith('http://')):
        namespace.account_endpoint = 'https://' + namespace.account_endpoint
        namespace.account_endpoint = namespace.account_endpoint.rstrip('/')
    # if account name is specified but no key, attempt to query if we use shared key auth
    if namespace.account_name and namespace.account_endpoint and not namespace.account_key:

        # check to see if we are using the default credentials
        from azure.cli.core._profile import Profile
        profile = Profile(cli_ctx=cmd.cli_ctx)
        resource = cmd.cli_ctx.cloud.endpoints.batch_resource_id
        token_credential, _, _ = profile.get_login_credentials(resource=resource)

        # if not we query for the account key
        if token_credential is None:
            if cmd.cli_ctx.config.get('batch', 'auth_mode', 'shared_key') == 'shared_key':
                endpoint = urlsplit(namespace.account_endpoint)
                host = endpoint.netloc
                client = get_mgmt_service_client(cmd.cli_ctx, BatchManagementClient)
                acc = next((x for x in client.batch_account.list()
                           if x.name == namespace.account_name and x.account_endpoint == host), None)
                if acc:
                    from azure.mgmt.core.tools import parse_resource_id
                    rg = parse_resource_id(acc.id)['resource_group']
                    namespace.account_key = \
                        client.batch_account.get_keys(rg,  # pylint: disable=no-member
                                                      namespace.account_name).primary
                else:
                    raise ValueError(f"Batch account '{namespace.account_name}' not found.")
    else:
        if not namespace.account_name:
            raise ValueError("Specify batch account in command line or environment variable.")
        if not namespace.account_endpoint:
            raise ValueError("Specify batch endpoint in command line or environment variable.")

    if cmd.cli_ctx.config.get('batch', 'auth_mode', 'shared_key') == 'aad':
        namespace.account_key = None
