# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
#
# Code generated by aaz-dev-tools
# --------------------------------------------------------------------------------------------

# pylint: skip-file
# flake8: noqa

from azure.cli.core.aaz import *


@register_command_group(
    "network network-watcher",
)
class __CMDGroup(AAZCommandGroup):
    """Manage network watcher and its sub-resources.

    Network Watcher provides tools to monitor, diagnose, and view connectivity-related metrics for your Azure deployments.
    """
    pass


__all__ = ["__CMDGroup"]
