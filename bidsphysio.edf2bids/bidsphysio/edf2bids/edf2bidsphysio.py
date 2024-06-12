"""
Purpose
----
Read eye tracking data from an SR Reasearch .edf file and return a
BIDS physiology recording object and as BIDS events object.
It uses "pyedfread" to read the EDF file.
    
Usage
----
edf2bidsphysio.py -i <EDF Eyetracking Data> -b <BIDS file prefix> -e <Save eye-motion events>
    
Authors
----
Chrysa Papadaniil, NYU Center for Brain Imaging
    
Dates
----
2020-09-04

References
----
EDF reader: https://github.com/nwilming/pyedfread
BIDS specification for physio signal:
https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/06-physiological-and-other-continuous-recordings.html
    
License
----
MIT License
Copyright (c) 2020      Pablo Velasco
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights 
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import argparse
import json
import os
import sys
import numpy as np
import pandas as pd
import re

pd.options.mode.chained_assignment = None

from pyedfread import edf
from pyedfread import edfread

from bidsphysio.base.bidsphysio import PhysioSignal, PhysioData
from bidsphysio.events.eventsbase import EventSignal, EventData

# Function to find the a particular line in a raw edf file's messages
def find_line_with_string(input_text, input_string):
    # returns only the first line containing the input string
    for line in range(len(input_text)):
        if input_string in input_text[line]:
            found_line = line
            break
        else:
            found_line = None
    return found_line


def edf2bids(physio_edf, path_metadata, skip_eye_events=False):
    """Reads the EDF file and saves the continuous eye movement data in a PhysioData member

    Parameters
    ----------
    physio_edf : str
        Path to the original EDF file
    skip_eye_events : bool
        Option to save eye motion events (fixations, saccades and blinks). Default is True.

    Returns
    -------
    physio : PhysioData
        PhysioData with the contents of the file
    """
    # Read EDF data into three pandas dataframes
    samples, events, messages = edf.pread(physio_edf)

    # First we will work on our physio signal
    # Remove rows that only have zero values
    samples = samples.loc[~(samples == 0).all(axis=1)]

    # Create a new column to hold the original samples
    samples["samples"] = samples["time"]

    # Turn time to seconds and adjust time so that it starts at 0
    samples.time = (samples.time - samples.time[0]) / 1000
    sample_times = samples.time.values.tolist()

    # Find sampling frequency and which eye was recorded from messages
    message = edfread.read_messages(physio_edf)

    line_end_header=find_line_with_string(message,b"!MODE RECORD")


    cleaned_header = [line.decode('utf-8', errors='ignore').strip(' \n\x00') for line in message[0:line_end_header] if line]
    cleaned_header = [re.sub(r'\s{5,}', '    ', line) for line in cleaned_header]
    EDFHeader = '[' + ', '.join(map(repr, cleaned_header)) + ']'


    #detect if calibration is in the messages:
    line_calibration=find_line_with_string(message,b"CALIBRATION (")
    line_error = find_line_with_string(message, b"ERROR")
    stop_time=samples['samples'].values.tolist()[-1]
    start_time=samples['samples'].values.tolist()[0]
    if (line_calibration is not None) and (line_error is not None):
        line_error=find_line_with_string(message, b"ERROR")
        average_calibration_error=message[line_error].split()[7].decode("utf-8")
        max_calibration_error=message[line_error].split()[9].decode("utf-8")

        calibration_count = 1
        if 'HV9' in message[line_calibration].decode("utf-8").upper():
            calibration_type='HV9'
            calibration_position='[[400,300],[400,51],[400,549],[48,300],[752,300],[48,51],[752,51],[48,549],[752,549]]'
        else:
            pass

    else:
        calibration_count = 0



    RECCFG_line = find_line_with_string(message, b"RECCFG")
    sampling_frequency = message[RECCFG_line].split()[2].decode("utf-8")
    which_eye = message[RECCFG_line].split()[5].decode("utf-8")
    ELCL_PROC_line = find_line_with_string(message, b"ELCL_PROC")
    pupil_fit_method = (
        "ellipse"
        if "ELLIPSE" in message[ELCL_PROC_line].split()[1].decode("utf-8").upper()
        else "center-of-mass"
    )
    threshold_line = find_line_with_string(message, b"THRESHOLDS")
    pupil_threshold = message[threshold_line].split()[2].decode("utf-8")
    CR_threshold = message[threshold_line].split()[3].decode("utf-8")
    CR_threshold = CR_threshold.replace('\u0000', '')
    eye_tracking_method = (
        "P-CR"
        if "CR" in message[RECCFG_line].split()[1].decode("utf-8")
        else message[RECCFG_line].split()[1].decode("utf-8")
    )

    # Define columns to save: We are saving gaze, pupil area size, trigger, and optionally fixations, saccades and blinks but we can modify it to include head reference coordinates, velocities etc.
    samples = samples.rename(columns={"input": "trigger"})
    # TODO: Rename other columns?
    if which_eye == "R\x00":
        samples = samples.rename(
            columns={
                "samples": "eye_timestamp",
                "gx_right": "eye1_x_coordinate",
                "gy_right": "eye1_y_coordinate",
                "pa_right": "eye1_pupil_size",
            },
            errors="raise",
        )
        column_list = [
            "eye_timestamp",
            "eye1_x_coordinate",
            "eye1_y_coordinate",
            "eye1_pupil_size",
            "trigger",
        ]
        recorded_eye = "Right"
    elif which_eye == "L\x00":
        samples = samples.rename(
            columns={
                "samples": "eye_timestamp",
                "gx_left": "eye1_x_coordinate",
                "gy_left": "eye1_y_coordinate",
                "pa_left": "eye1_pupil_size",
            }
        )
        column_list = [
            "eye_timestamp",
            "eye1_x_coordinate",
            "eye1_y_coordinate",
            "eye1_pupil_size",
            "trigger",
        ]
        recorded_eye = "Left"
    elif which_eye == "LR\x00":
        samples = samples.rename(
            columns={
                "samples": "eye_timestamp",
                "gx_left": "eye1_x_coordinate",
                "gy_left": "eye1_y_coordinate",
                "pa_left": "eye1_pupil_size",
                "gx_right": "eye2_x_coordinate",
                "gy_right": "eye2_y_coordinate",
                "pa_right": "eye2_pupil_size",
            }
        )
        column_list = [
            "eye_timestamp",
            "eye1_x_coordinate",
            "eye1_y_coordinate",
            "eye2_x_coordinate",
            "eye2_y_coordinate",
            "eye1_pupil_size",
            "eye2_pupil_size",
            "trigger",
        ]
        recorded_eye = "Both"

    # If wanted, save fixations, saccades and blinks in additional columns
    if skip_eye_events == False:
        samples["fixation"] = 0
        samples["saccade"] = 0
        samples["blink"] = 0

        for ind, value in enumerate(events.type):
            ind_s = samples[samples["eye_timestamp"] == events.start[ind]].index.values
            ind_e = samples[samples["eye_timestamp"] == events.end[ind]].index.values
            if value == "fixation":
                samples.fixation[int(ind_s) : int(ind_e)] = 1
            if value == "saccade":
                samples.saccade[int(ind_s) : int(ind_e)] = 1
                if events.blink[ind] == True:
                    if which_eye == "R\x00":
                        gaze_with_sacc = samples.eye1_x_coordinate[
                            int(ind_s) : int(ind_e)
                        ]
                    ind_bs = gaze_with_sacc[
                        gaze_with_sacc == 100000000.0
                    ].first_valid_index()
                    ind_be = gaze_with_sacc[
                        gaze_with_sacc == 100000000.0
                    ].last_valid_index()
                    if ind_bs is not None and ind_be is not None:
                        samples.blink[int(ind_bs) : int(ind_be or -1)] = 1
                    else:
                        print(f"Found blink with start={ind_bs} and end={ind_be}")

        optional_columns = ["fixation", "saccade", "blink"]
        column_list.extend(optional_columns)

    # Init physiodata object to hold physio signals
    physio = PhysioData()

    # Go through the columns and keep the signals we are interested in. Value -32768.0 indicates missing values
    for wc in range(len(column_list)):
        indc = np.where(column_list[wc] == samples.columns)[0]
        physio_label = samples.columns[indc][0]
        s = samples[samples.columns[indc][0]].values.tolist()

        if not (
            (samples[samples.columns[indc][0]] == 0.0).all()
            or (samples[samples.columns[indc][0]] == 127.0).all()
            or (samples[samples.columns[indc][0]] == 32768.0).all()
            or (samples[samples.columns[indc][0]] == -32768.0).all()
        ):

            physio.append_signal(
                PhysioSignal(
                    label=physio_label,
                    samples_per_second=int(sampling_frequency),
                    sampling_times=sample_times,
                    signal=s,
                )
            )

    # Add "RecordedEye" as an attribute to the physio object so as to save it in the .json file
    if calibration_count==0:
        attributes_new = {
            "RecordedEye": recorded_eye,
            "EyeTrackingMethod": eye_tracking_method,
            "PupilFitMethod": pupil_fit_method,
            "CRThreshold": CR_threshold,
            "PThreshold": pupil_threshold,
            "MetadataJson": path_metadata,
            "CalibrationCount":calibration_count,
            "StartTime":start_time,
            "StopTime":stop_time,
            "EDFHeader":EDFHeader,
        }
    else:
        attributes_new = {
            "RecordedEye": recorded_eye,
            "EyeTrackingMethod": eye_tracking_method,
            "PupilFitMethod": pupil_fit_method,
            "CRThreshold": CR_threshold,
            "PThreshold": pupil_threshold,
            "MetadataJson": path_metadata,
            "CalibrationCount":calibration_count,
            "CalibrationType":calibration_type,
            "CalibrationPosition":calibration_position,
            "AverageCalibrationError":average_calibration_error,
            "MaximalCalibrationError":max_calibration_error,
            "StartTime": start_time,
            "StopTime": stop_time,
            "EDFHeader": EDFHeader,
        }




    for attr, value in attributes_new.items():
        setattr(physio, attr, value)

    # Define neuralstarttime and physiostartime as the first trigger time and first sample time, respectively.
    signal_labels = [l.lower() for l in physio.labels()]
    if "trigger" in signal_labels:
        physio.digitize_trigger()
        nstarttime = physio.get_trigger_timing()[0]
        pstartime = samples.time[0]
        for p_signal in physio.signals:
            p_signal.neuralstarttime = nstarttime
            p_signal.physiostartime = pstartime
            # we also fill with NaNs the places for which there is missing data:
            p_signal.plug_missing_data()
    else:
        print("No trigger channel was found")

    return physio


def edfevents2bids(physio_edf):
    """Reads the EDF file and saves the task events in a EventData member. Task events are the string messages that the user sends to the eyetracker to identify experimental conditions.

    Parameters
    ----------
    physio_edf : str
        Path to the original EDF file

    Returns
    -------
    event : EventData
        EventData with the contents of the file
    """

    # Read messages sent to the eyetracker
    message = edfread.read_messages(physio_edf)

    MR_line = find_line_with_string(
        message, b"!MODE RECORD"
    )  # sent messages appear after line of "MODE RECORD"
    sent_messages = np.unique(edfread.read_messages(physio_edf)[MR_line + 1 :])
    EventIdentifiers = []
    for sm in sent_messages:
        EventIdentifiers.append(sm)

    # Read the EDF data into three pandas dataframes including the messages
    samples, events, all_messages = edf.pread(physio_edf, trial_marker=b"")

    if all_messages.empty:
        event = []
        print("No task events were found")
    else:
        all_messages = all_messages.dropna(subset=["trialid "])

        # Create a new column to hold the original samples
        all_messages["sample"] = all_messages["trialid_time"]
        all_messages["sample"] = all_messages["sample"].apply(np.int64)
        all_messages.trialid_time = all_messages.trialid_time / 1000
        all_messages.trialid_time = all_messages.trialid_time - samples.time[0] / 1000
        # change names of messages columns to be consistent with events columns names
        all_messages.columns = [
            "onset" if x == "trialid_time" else "trial_type" if x == "trialid " else x
            for x in all_messages.columns
        ]

        # Create duration column and make it equal to 0 for now
        all_messages["duration"] = 0

        # If a trigger channel is available in the edf recording, adjust onset to be measured with respect to the first trigger
        samples = samples.loc[~(samples == 0).all(axis=1)]
        samples.time = (samples.time - samples.time[0]) / 1000
        if not (
            (samples["input"] == 0.0).all()
            or (samples["input"] == 127.0).all()
            or (samples["input"] == 32768.0).all()
            or (samples["input"] == -32768.0).all()
        ):
            tmp = np.array(samples.input)
            counts, bin_edges = np.histogram(
                tmp[~np.isnan(tmp)], bins=10, range=[min(tmp), max(tmp)]
            )
            first_bin = bin_edges[np.argmax(counts)] + (bin_edges[1] - bin_edges[0]) / 2
            counts[np.argmax(counts)] = 0
            second_bin = (
                bin_edges[np.argmax(counts)] + (bin_edges[1] - bin_edges[0]) / 2
            )
            threshold = (first_bin + second_bin) / 2
            dg_signal = tmp
            dg_signal[tmp < threshold] = 0
            dg_signal[tmp > threshold] = 1
            dg_signal[np.isnan(tmp)] = 0
            ind_trig = (dg_signal != 0.0).argmax()
            all_messages["onset"] = all_messages["onset"] - samples.time[ind_trig]
        else:
            print(
                "No trigger channel was found and the onsets are not trigger-adjusted"
            )

        # Init eventdata object to hold event signals
        event = EventData()

        # Create a list of the columns we want to keep
        event_column_list = ["onset", "duration", "trial_type", "sample"]

        for ec in range(len(event_column_list)):
            indc_e = np.where(event_column_list[ec] == all_messages.columns)[0]
            event_label = all_messages.columns[indc_e][0]
            es = all_messages[all_messages.columns[indc_e][0]]

            if not (all_messages[all_messages.columns[indc_e][0]] == 0.0).all():
                if event_label in {"onset", "duration"}:
                    event_units = "seconds"
                    event_type = "float"
                elif event_label == "sample":
                    event_type = "int"
                elif event_label == "trial_type":
                    event_type = "str"
                    event_units = ""
                    # event_description = 'String sent to eyetracker to identify event of interest'

            event.append_event(
                EventSignal(
                    label=event_label,
                    units=event_units,
                    # description = event_description,
                    event=es,
                    type=event_type,
                )
            )

    return event


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Convert Eyetracker EDF physiology files to BIDS-compliant physiology recording"
    )
    parser.add_argument(
        "-i", "--infile", required=True, help="SR research eye tracker EDF file"
    )
    parser.add_argument(
        "-m",
        "--metadata",
        required=True,
        help="path to json file with metadata of the eyetracking experiment",
    )
    parser.add_argument(
        "-b",
        "--bidsprefix",
        required=True,
        help="Prefix of the BIDS file. It should match the _bold.nii.gz",
    )
    parser.add_argument(
        "-e",
        "--skip_eye_events",
        action="store_true",
        help="Skips saving eye-motion events (fixations, saccades and blinks) as estimated by Eyelink algorithms",
    )
    args = parser.parse_args()

    # make sure input file exists:
    if not os.path.exists(args.infile):
        raise FileNotFoundError("{i} file not found".format(i=args.infile))

    # make sure output directory exists:
    odir = os.path.dirname(args.bidsprefix)
    if not os.path.exists(odir):
        os.makedirs(odir)
    physio_data = edf2bids(args.infile, args.metadata, args.skip_eye_events)
    event_data = edfevents2bids(args.infile)

    signal_labels = [l.lower() for l in physio_data.labels()]
    if "trigger" in signal_labels:
        physio_data.save_to_bids_with_trigger(args.bidsprefix)
    else:
        physio_data.save_to_bids(args.bidsprefix)

    event_data.save_events_bids_data(
        args.bidsprefix + "_eventlist_raw"
    )  


# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
    main()
