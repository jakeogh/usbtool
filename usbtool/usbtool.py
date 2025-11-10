#!/usr/bin/env python3
# -*- coding: utf8 -*-
# tab-width:4


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
from asserttool import minone
from click_auto_help import AHGroup
from clicktool import CONTEXT_SETTINGS
from clicktool import click_add_options
from clicktool import click_global_options
from clicktool import tvicgvd
from eprint import eprint
from globalverbose import gvd
from mptool import output
from serialtool import SerialMinimal
from timetool import get_year_month_day

signal(SIGPIPE, SIG_DFL)

DATA_DIR = Path(os.path.expanduser("~")) / Path(".usbtool") / Path(get_year_month_day())
DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_attributes(device: Path) -> str:
    try:
        _ = sh.udevadm("info", "--attribute-walk", device.as_posix())
    except sh.ErrorReturnCode_1 as e:
        icp(e)
        raise ValueError(device)
    return _


def get_serial_number_for_device(device: Path) -> str:
    _ = get_attributes(device)
    _lines = _.splitlines()
    for _l in _lines:
        _l = _l.strip()
        if _l.startswith("ATTRS{serial}=="):
            serial = _l.split('"')[1]
            return serial
    raise ValueError(device)


def get_manufacturer_for_device(device: Path) -> str:
    _ = get_attributes(device)
    _lines = _.splitlines()
    for _l in _lines:
        _l = _l.strip()
        if _l.startswith("ATTRS{manufacturer}=="):
            mfg = _l.split('"')[1]
            return mfg
    raise ValueError(device)


def get_usb_id_dict():
    ids = {}
    _ = sh.lsusb()
    _lines = _.splitlines()
    for _l in _lines:
        _id = _l.split("ID ")[1].split(" ")[0]
        _description = " ".join(_l.split("ID ")[1].split(" ")[1:])
        ids[_id] = _description
    return ids


def get_usb_tty_device_list() -> list[Path]:
    _bus_path = Path("/sys/bus/usb-serial/devices/")
    _device_list = [Path(_) for _ in _bus_path.iterdir()]
    _acm_device_list = [
        Path(_)
        for _ in Path("/dev/").iterdir()
        if _.as_posix().startswith("/dev/ttyACM")
    ]
    ic(_device_list)
    ic(_acm_device_list)
    _ = _device_list + _acm_device_list
    return _


def get_usb_id_for_device(device: Path) -> str:
    _ = get_attributes(device)
    _lines = _.splitlines()
    for index, _l in enumerate(_lines):
        _l = _l.strip()
        if _l.startswith("ATTRS{idProduct}=="):
            id_product = _l.split('"')[1]
            id_vendor = _lines[index + 1].split('"')[1]
            usb_id = f"{id_vendor}:{id_product}"
            return usb_id
    raise ValueError(device)


def get_devices() -> list[Path]:
    _tty_list = get_usb_tty_device_list()
    _devices = [Path(f"/dev/{_.name}") for _ in _tty_list]
    return _devices


def get_devices_for_usb_id(usb_id) -> list[Path]:
    devices = []
    assert len(usb_id) == 9
    assert ":" in usb_id
    assert usb_id in get_usb_id_dict().keys()

    _device_list = get_usb_tty_device_list()
    for _ in _device_list:
        _id = get_usb_id_for_device(_)
        if _id == usb_id:
            devices.append(Path("/dev/{_.name}"))

    if devices:
        return devices
    raise ValueError(usb_id)


def find_device(
    *,
    baud_rate: int,
    timeout: int = 1,
    command_hex: str | None = None,
    response_hex: str | None = None,
    usb_id: str | None = None,
    serial_number: str | None = None,
    manufacturer: str | None = None,
    log_serial_data: bool = False,
    data_dir: Path = DATA_DIR,
):

    minone([command_hex, usb_id, serial_number, manufacturer])

    if command_hex:
        if not response_hex:
            raise ValueError(
                "passing a command_hex argument requires that response_hex argument also be specified."
            )

    if usb_id:
        _devices = get_devices_for_usb_id(usb_id)
    else:
        _devices = get_devices()

    icp(_devices)

    for _ in _devices:
        if serial_number:
            try:
                _serial_number = get_serial_number_for_device(_)
                if _serial_number != serial_number:
                    # serial does not match, go to next device
                    continue
            except AttributeError:
                # device does not have a serial attribute, skip to next device
                continue

        if manufacturer:
            try:
                _manufacturer = get_manufacturer_for_device(_)
                if _manufacturer != manufacturer:
                    # manufacturer does not match, go to next device
                    continue
            except AttributeError:
                # device does not have a manufacturer attribute, skip to next device
                continue

        if command_hex:
            _tx_bytes = bytes.fromhex(command_hex)
            try:
                serial_oracle = SerialMinimal(
                    data_dir=data_dir,
                    log_serial_data=log_serial_data,
                    serial_port=_.as_posix(),
                    baud_rate=baud_rate,
                    default_timeout=timeout,
                )
            except PermissionError as e:
                ic(e)
                eprint(
                    "ERROR: PermissionError on port {_.as_posix()} (Skipped searching this port)"
                )
                continue

            _bytes_written = serial_oracle.ser.write(_tx_bytes)
            assert _bytes_written == len(_tx_bytes)
            eprint(f"{_tx_bytes=}")
            _expected_rx_bytes = bytes.fromhex(response_hex)
            _bytes_read = serial_oracle.ser.readall()
            eprint(f"{_bytes_read=}", f"{_expected_rx_bytes=}")
            if _bytes_read != _expected_rx_bytes:
                # not a match, skip to next
                # bug more than one device may match
                continue

        # all checks passed, found the correct device
        icp(_)
        return _

    raise ValueError(
        f"Error: No matching device found for {command_hex=} {response_hex=} {baud_rate=} {usb_id=} {serial_number=} {manufacturer=} {timeout=}"
    )


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
        output(
            _.as_posix(),
            reason=None,
            tty=tty,
            dict_output=False,
        )


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
        output(
            _,
            reason=None,
            tty=tty,
            dict_output=False,
        )


@cli.command("find-device")
@click.option("--command-hex", type=str)
@click.option("--response-hex", type=str)
@click.option("--usb-id")
@click.option("--serial-number")
@click.option("--manufacturer")
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
    serial_number: str,
    manufacturer: str,
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

    if command_hex:
        if not response_hex:
            raise ValueError(
                f"{command_hex=} requires --response-hex to be specified as well."
            )

    _ = find_device(
        command_hex=command_hex,
        response_hex=response_hex,
        baud_rate=baud_rate,
        timeout=timeout,
        usb_id=usb_id,
        serial_number=serial_number,
        manufacturer=manufacturer,
        log_serial_data=log_serial_data,
        data_dir=data_dir,
    )

    if _:
        output(
            _.as_posix(),
            reason=None,
            tty=tty,
            dict_output=False,
        )


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
        output(
            f"{_id} {_description}",
            reason=None,
            tty=tty,
            dict_output=False,
        )
