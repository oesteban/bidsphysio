import pytest
from os.path import join as pjoin
from glob import glob
from bidsphysio import bidsphysio

###  Globals   ###

SAMPLES_PER_SECOND = 5
PHYSIO_START_TIME = 10
SAMPLES_COUNT = 100
LABELS = ['signal1', 'signal2', 'signal3']


###   TESTS FOR CLASS "physiosignal"   ###

@pytest.fixture
def mySignal():
    """    Simulate a physiosignal object    """

    mySignal=bidsphysio.physiosignal(
                 label='simulated',
                 samples_per_second=SAMPLES_PER_SECOND,
                 physiostarttime=PHYSIO_START_TIME,
                 signal= SAMPLES_COUNT * [0]     # fill with zeros
             )

    return mySignal


@pytest.fixture
def trigger_timing(
        scannerdelay=2,
        TR=0.75
):
    """   Simulate trigger timing (times at which the triggers were sent   """
    t_first_trigger = PHYSIO_START_TIME + scannerdelay
    trigger_timing = [t_first_trigger + TR * i for i in range(SAMPLES_COUNT)]

    return trigger_timing


def test_calculate_trigger_events(
        mySignal, trigger_timing
):
    """
    Make sure you get as many triggers in the trigger signal
    as elements there are in the trigger timing (between the
    beginning of the recording and the end)
    """

    import numpy as np

    # calculate trigger events:
    trig_signal = mySignal.calculate_trigger_events( trigger_timing )

    assert isinstance(trig_signal, np.ndarray)

    # calculate how many triggers there are between the first and last sampling_times:
    num_trig_within_physio_samples = np.bitwise_and(
                np.array(trigger_timing) >= mySignal.sampling_times[0],
                np.array(trigger_timing) <= mySignal.sampling_times[-1]
    )
    
    assert ( sum(trig_signal) == sum(num_trig_within_physio_samples) )


def test_matching_trigger_signal(
        mySignal,
        trigger_timing
):
    """
    Test that both physiosignals (the original signal and the derived one with the trigger)
    have the same fields.
    It requires the result of "test_calculate_trigger_events"
    """

    # calculate trigger events:
    trig_signal = mySignal.calculate_trigger_events( trigger_timing )

    trigger_physiosignal = bidsphysio.physiosignal.matching_trigger_signal(mySignal, trig_signal)

    assert isinstance(trigger_physiosignal, bidsphysio.physiosignal)
    assert trigger_physiosignal.label == 'trigger'
    assert trigger_physiosignal.samples_per_second == mySignal.samples_per_second
    assert trigger_physiosignal.physiostarttime == mySignal.physiostarttime
    assert trigger_physiosignal.neuralstarttime == mySignal.neuralstarttime
    assert trigger_physiosignal.sampling_times == mySignal.sampling_times
    assert all(trigger_physiosignal.signal == trig_signal)


###   TESTS FOR CLASS "physiodata"   ###

@pytest.fixture
def myphysiodata():
    """   Create a "physiodata" object with barebones content  """

    myphysiodata = bidsphysio.physiodata(
                [ bidsphysio.physiosignal(
                    label = l,
                    samples_per_second = 1,
                    physiostarttime = 0,
                    signal = [i for i in range(10)]
                ) for l in LABELS ]
            )
    return myphysiodata


@pytest.fixture
def simulated_trigger_signal():
    """
    Simulates the recordings for the scanner trigger
    """
    return [0 if i%5 else 1 for i in range(10)]


@pytest.fixture
def myphysiodata_with_trigger(
        simulated_trigger_signal
):
    myphysiodata_with_trigger = bidsphysio.physiodata(
                [ bidsphysio.physiosignal(
                    label = l,
                    samples_per_second = 1,
                    physiostarttime = 0,
                    signal = [i for i in range(10)]
                ) for l in LABELS ]
            )

    # add a trigger signal to the physiodata_with_trigger:
    trigger_start_time = 0
    trigger_sampling_rate = 5
    myphysiodata_with_trigger.append_signal(
        bidsphysio.physiosignal(
            label = 'trigger',
            samples_per_second = trigger_sampling_rate,
            physiostarttime = trigger_start_time,
            signal = simulated_trigger_signal
        )
    )
    return myphysiodata_with_trigger


def test_physiodata_labels(
        myphysiodata
):
    """
    Test both the physiodata constructor and that
    physiodata.labels() returns the labels of the physiosignals
    """

    assert myphysiodata.labels() == LABELS


def test_append_signal(
        myphysiodata
):
    """
    Tests that "append_signal" does what it is supposed to do
    """

    myphysiodata.append_signal(
        bidsphysio.physiosignal( label = 'extra_signal' )
    )

    mylabels = LABELS
    mylabels.append('extra_signal')
    assert myphysiodata.labels() == mylabels


def test_save_bids_json(
            tmpdir,
            myphysiodata
    ):
    """
    Tests  "save_bids_json"
    """

    import json

    json_file_name = pjoin(tmpdir.strpath,'foo.json')

    # make sure it gives an error if sampling or t_start are not the same for all physiosignals
    # samples_per_second:
    myphysiodata.signals[0].samples_per_second = 2
    with pytest.raises(Exception) as e_info:
        myphysiodata.save_bids_json(json_file_name)

    # now, set the sampling rate back like the rest and test the t_start:
    myphysiodata.signals[0].samples_per_second = myphysiodata.signals[1].samples_per_second
    myphysiodata.signals[0].physiostarttime = 1
    with pytest.raises(Exception) as e_info:
        myphysiodata.save_bids_json(json_file_name)

    # set all t_start to the same (by fixing the physiostarttime:
    myphysiodata.signals[0].physiostarttime = myphysiodata.signals[1].physiostarttime

    # make sure the filename ends with "_physio.json"
    myphysiodata.save_bids_json(json_file_name)
    json_files = glob(pjoin(tmpdir,'*.json'))
    assert len(json_files)==1
    json_file = json_files[0]
    assert json_file.endswith('_physio.json')

    # read the json file and check the content vs. the physiodata:
    with open(json_file) as f:
        d = json.load(f)
    assert d['Columns'] == LABELS
    assert d['SamplingFrequency'] == myphysiodata.signals[0].samples_per_second
    assert d['StartTime'] == myphysiodata.signals[0].physiostarttime


def test_save_bids_data(
        tmpdir,
        myphysiodata
):
    """
    Tests  "save_bids_data"
    """
    import gzip

    data_file_name = pjoin(tmpdir.strpath,'foo.tsv')

    # make sure the filename ends with "_physio.tsv.gz"
    myphysiodata.save_bids_data(data_file_name)
    data_files = glob(pjoin(tmpdir,'*.tsv*'))
    assert len(data_files)==1
    data_file = data_files[0]
    assert data_file.endswith('_physio.tsv.gz')

    # read the data file and check the content vs. the physiodata:
    with gzip.open(data_file,'rt') as f:
        for idx,line in enumerate(f):
            assert [float(s) for s in line.split('\t')] == [s.signal[idx] for s in myphysiodata.signals]


def test_save_to_bids(
        tmpdir,
        myphysiodata
):
    """
    Test "save_to_bids"
    """
    from os import remove

    output_file_name = pjoin(tmpdir.strpath,'foo')

    # when all sample rates and t_starts are the same, there should be only one
    #   (.sjon/.tsv.gz) pair:
    myphysiodata.save_to_bids(output_file_name)
    json_files = glob(pjoin(tmpdir,'*.json'))
    assert len(json_files)==1
    json_file = json_files[0]
    assert json_file.endswith('_physio.json')
    data_files = glob(pjoin(tmpdir,'*.tsv*'))
    assert len(data_files)==1
    data_file = data_files[0]
    assert data_file.endswith('_physio.tsv.gz')
    remove(json_file)
    remove(data_file)

    # make the last signal different from the rest, so that it is saved
    #   in a separate file:
    myphysiodata.signals[-1].samples_per_second *= 2
    myphysiodata.save_to_bids(output_file_name)
    json_files = glob(pjoin(tmpdir,'*.json'))
    assert len(json_files)==2
    # make sure one of them ends with "_recording-" plus the label of the last signal, etc:
    assert [jf for jf in json_files if jf.endswith('_recording-{s3}_physio.json'.format(s3=LABELS[-1]))]
    data_files = glob(pjoin(tmpdir,'*.tsv*'))
    assert len(data_files)==2
    # make sure one of them ends with "_recording-" plus the label of the last signal, etc:
    assert [df for df in data_files if df.endswith('_recording-{s3}_physio.tsv.gz'.format(s3=LABELS[-1]))]


def test_get_trigger_timing(
        myphysiodata,
        simulated_trigger_signal,
        myphysiodata_with_trigger
):
    # try it on a physiodata without trigger signal:
    with pytest.raises(ValueError) as e_info:
        myphysiodata.get_trigger_timing()
        assert str(e_info.value) == "'trigger' is not in list"

    # try with physiodata_with_trigger
    trigger_start_time = 0
    trigger_sampling_rate = 5
    assert myphysiodata_with_trigger.get_trigger_timing() == [
                                trigger_start_time + idx / trigger_sampling_rate
                                   for idx, trig in enumerate(simulated_trigger_signal) if trig == 1
                         ]

