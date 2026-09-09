#!/usr/bin/env python3
"""Smoke tester for HungerBridge BridgeClient.

Usage:
  python hungerlib/tests/script.py --base http://localhost:8080 --id ID --secret SECRET [--allow-actions]

Reads defaults from env: HUNGER_BASE, HUNGER_ID, HUNGER_SECRET
"""
import os
import time
import argparse
import json
from pprint import pprint

from hungerlib.bridgeclient import BridgeClient


def safe_call(name, fn, *a, **kw):
    print('\n=== {} ==='.format(name))
    try:
        res = fn(*a, **kw)
        try:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        except Exception:
            pprint(res)
    except Exception as e:
        print('ERROR:', type(e).__name__, str(e))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--base', default=os.getenv('HUNGER_BASE', 'http://localhost:8080'))
    p.add_argument('--id', default=os.getenv('HUNGER_ID'))
    p.add_argument('--secret', default=os.getenv('HUNGER_SECRET'))
    p.add_argument('--allow-actions', action='store_true', help='Allow destructive actions (stop/restart/run raw)')
    p.add_argument('--timeout', type=float, default=2.0, help='Stream connect wait seconds')
    args = p.parse_args()

    print('Base URL:', args.base)

    client = BridgeClient(args.base, args.id, args.secret)

    # Basic
    safe_call('ping', client.ping)
    safe_call('getPing (client RTT ms)', client.getPing)

    # Auth & metadata
    safe_call('authCheck (full)', client.authCheck)
    safe_call('serverInfo (full)', client.serverInfo)
    safe_call('serverMeta (full)', client.serverMeta)
    safe_call('serverStatus (full)', client.serverStatus)

    # Bridge convenience
    safe_call('getBridge (full)', client.getBridge)
    safe_call('getVersion', client.getVersion)
    safe_call('getPlatform', client.getPlatform)
    safe_call('getMinecraftVersion', client.getMinecraftVersion)

    # Players
    safe_call('getPlayers (full)', client.getPlayers)
    safe_call("getPlayers('count')", lambda: client.getPlayers('count'))
    safe_call("getPlayers('players')", lambda: client.getPlayers('players'))

    # World
    safe_call("getTPS('current')", lambda: client.getTPS('current'))
    safe_call("getTPS('1m')", lambda: client.getTPS('1m'))
    safe_call("getTPS('5m')", lambda: client.getTPS('5m'))
    safe_call("getTPS('tick_time')", lambda: client.getTPS('tick_time'))
    safe_call('getMSPT', client.getMSPT)
    safe_call('getLoadedChunks', client.getLoadedChunks)
    safe_call('getWorldTime', client.getWorldTime)
    safe_call('getWorldWeather', client.getWorldWeather)

    # System
    safe_call('getSystemUptime', client.getSystemUptime)
    safe_call('getSystemCpu', client.getSystemCpu)
    safe_call('getSystemMemory', client.getSystemMemory)
    safe_call('getSystemDisk', client.getSystemDisk)

    # Logging
    safe_call("log(level='info')", lambda: client.log('smoke test log', 'info'))
    safe_call('log(level=None) (backspace trick)', lambda: client.log('smoke test no-level', None))

    # runCommand: normalized
    safe_call("runCommand(normalize=True)", lambda: client.runCommand('list', normalize=True))
    if args.allow_actions:
        safe_call("runCommand(normalize=False)", lambda: client.runCommand('list', normalize=False))
    else:
        print('\nSkipping raw runCommand (use --allow-actions to enable)')

    # Stream (non-blocking short connect)
    print('\n=== stream connect (short) ===')
    try:
        client.stream.connect(history=1)
        time.sleep(args.timeout)
        print('stream isConnected:', client.stream.isConnected())
        print('sanitized lines (count):', len(client.stream.getSanitized()))
        print('timestamped entries (count):', len(client.stream.getTimestamped()))
    except Exception as e:
        print('stream error:', type(e).__name__, str(e))
    finally:
        try:
            client.stream.disconnect()
        except Exception:
            pass

    # Actions that may be destructive
    if args.allow_actions:
        safe_call('stopServer', client.stopServer)
        safe_call('restartServer', client.restartServer)
    else:
        print('\nSkipping stop/restart (use --allow-actions to enable)')

    print('\nDone.')


if __name__ == '__main__':
    main()
