#!/bin/bash

bash "$${STEAMCMDDIR}/steamcmd.sh" +login anonymous +quit

bash "$${SERVERDIR}/$target.sh" "$$@"
