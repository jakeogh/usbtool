#!/usr/bin/env python3
# -*- coding: utf8 -*-
# tab-width:4

# pylint: disable=useless-suppression             # [I0021]
# pylint: disable=missing-docstring               # [C0111] docstrings are always outdated and wrong
# pylint: disable=missing-param-doc               # [W9015]
# pylint: disable=missing-module-docstring        # [C0114]
# pylint: disable=fixme                           # [W0511] todo encouraged
# pylint: disable=line-too-long                   # [C0301]
# pylint: disable=too-many-instance-attributes    # [R0902]
# pylint: disable=too-many-lines                  # [C0302] too many lines in module
# pylint: disable=invalid-name                    # [C0103] single letter var names, name too descriptive(!)
# pylint: disable=too-many-return-statements      # [R0911]
# pylint: disable=too-many-branches               # [R0912]
# pylint: disable=too-many-statements             # [R0915]
# pylint: disable=too-many-arguments              # [R0913]
# pylint: disable=too-many-nested-blocks          # [R1702]
# pylint: disable=too-many-locals                 # [R0914]
# pylint: disable=too-many-public-methods         # [R0904]
# pylint: disable=too-few-public-methods          # [R0903]
# pylint: disable=no-member                       # [E1101] no member for base
# pylint: disable=attribute-defined-outside-init  # [W0201]
# pylint: disable=too-many-boolean-expressions    # [R0916] in if statement

from __future__ import annotations

import logging
import os
from pathlib import Path
from signal import SIG_DFL
from signal import SIGPIPE
from signal import signal

import click
import sh
from asserttool import ic
from asserttool import icp
from click_auto_help import AHGroup
from clicktool import CONTEXT_SETTINGS
from clicktool import click_add_options
from clicktool import click_global_options
from clicktool import tvicgvd
from globalverbose import gvd
from mptool import output
from serialtool import SerialMinimal
from timetool import get_year_month_day

sh.mv = None  # use sh.busybox('mv'), coreutils ignores stdin read errors


# this should be earlier in the imports, but isort stops working
signal(SIGPIPE, SIG_DFL)

DATA_DIR = Path(os.path.expanduser("~")) / Path(".usbtool") / Path(get_year_month_day())
DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_usb_id_dict():
    ids = {}
    _ = sh.lsusb()
    _lines = _.splitlines()
    for _l in _lines:
        _id = _l.split("ID ")[1].split(" ")[0]
        _description = " ".join(_l.split("ID ")[1].split(" ")[1:])
        ids[_id] = _description
    return ids


def get_usb_tty_device_list() -> tuple[str, ...]:
    _bus_path = Path("/sys/bus/usb-serial/devices/")
    _device_list = tuple(_bus_path.iterdir())
    return _device_list


def get_usb_id_for_device(device) -> str:
    _ = sh.udevadm("info", "-a", device.as_posix())
    # ic(_)
    _lines = _.splitlines()
    for index, _l in enumerate(_lines):
        # ic(index, _l)
        _l = _l.strip()
        if _l.startswith("ATTRS{idProduct}=="):
            # ic(_l)
            id_product = _l.split('"')[1]
            # ic(id_product)
            id_vendor = _lines[index + 1].split('"')[1]
            # ic(id_vendor)
            usb_id = f"{id_vendor}:{id_product}"
            # ic(usb_id)
            return usb_id
    raise ValueError(device)


def get_devices() -> list[str]:
    _tty_list = get_usb_tty_device_list()
    _devices = [f"/dev/{_.name}" for _ in _tty_list]
    return _devices


def get_devices_for_usb_id(usb_id) -> list[str]:
    devices = []
    assert len(usb_id) == 9
    assert ":" in usb_id
    assert usb_id in get_usb_id_dict().keys()

    _device_list = get_usb_tty_device_list()
    for _ in _device_list:
        _id = get_usb_id_for_device(_)
        if _id == usb_id:
            devices.append(f"/dev/{_.name}")

    if devices:
        return devices
    raise ValueError(usb_id)


# @with_plugins(iter_entry_points('click_command_tree'))
@click.group(context_settings=CONTEXT_SETTINGS, no_args_is_help=True, cls=AHGroup)
@click_add_options(click_global_options)
@click.pass_context
def cli(
    ctx,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
) -> None:

    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )
    if verbose:
        logging.basicConfig(level=logging.INFO)


@cli.command()
@click_add_options(click_global_options)
@click.pass_context
def list_usb_tty_devices(
    ctx,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
) -> None:

    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    _device_list = get_usb_tty_device_list()
    for _ in _device_list:
        output(_.as_posix(), reason=None, tty=tty, dict_output=False)


@cli.command("get-devices-for-usb-id")
@click.argument("usb_id")
@click_add_options(click_global_options)
@click.pass_context
def _get_devices_for_usb_id(
    ctx,
    usb_id: str,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
) -> None:

    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    _devices = get_devices_for_usb_id(usb_id)
    for _ in _devices:
        output(_, reason=None, tty=tty, dict_output=False)


@cli.command("find-device")
@click.argument("command_hex", type=str)
@click.argument("response_hex", type=str)
@click.option("--usb-id")
@click.option(
    "--data-dir",
    type=click.Path(
        exists=True,
        dir_okay=True,
        file_okay=False,
        path_type=Path,
        allow_dash=False,
    ),
    default=DATA_DIR,
)
@click.option("--baud-rate", type=int, default=9600)
@click.option("--log-serial-data", is_flag=True)
@click.option("--timeout", type=int, default=1)
@click_add_options(click_global_options)
@click.pass_context
def _find_device(
    ctx,
    usb_id: str,
    data_dir: Path,
    command_hex: str,
    response_hex: str,
    baud_rate: int,
    log_serial_data: bool,
    timeout: int,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
) -> None:

    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    ser = None
    if command_hex:
        if not response_hex:
            raise ValueError(
                "--command-hex requires that --response-hex also be specified."
            )

    if usb_id:
        _devices = get_devices_for_usb_id(usb_id)
    else:
        _devices = get_devices()

    icp(_devices)

    for _ in _devices:
        if command_hex:
            _tx_bytes = bytes.fromhex(command_hex)
            serial = SerialMinimal(
                data_dir=data_dir,
                log_serial_data=log_serial_data,
                serial_port=_,
                baud_rate=baud_rate,
                default_timeout=timeout,
            )

            _bytes_written = serial.ser.write(_tx_bytes)
            assert _bytes_written == len(_tx_bytes)
            icp(_tx_bytes)
            _expected_rx_bytes = bytes.fromhex(response_hex)
            _bytes_read = serial.ser.readall()
            icp(_bytes_read, _expected_rx_bytes)
            if _bytes_read == _expected_rx_bytes:
                output(_, reason=None, tty=tty, dict_output=False)
                break  # bug more than one device may match


@cli.command("get-usb-ids")
@click_add_options(click_global_options)
@click.pass_context
def _get_usb_ids(
    ctx,
    verbose_inf: bool,
    dict_output: bool,
    verbose: bool = False,
) -> None:

    tty, verbose = tvicgvd(
        ctx=ctx,
        verbose=verbose,
        verbose_inf=verbose_inf,
        ic=ic,
        gvd=gvd,
    )

    _ = get_usb_id_dict()
    for _id, _description in _.items():
        output(f"{_id} {_description}", reason=None, tty=tty, dict_output=False)
