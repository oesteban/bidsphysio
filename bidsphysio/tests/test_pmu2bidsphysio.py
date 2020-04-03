'''   Tests for the module "pmu2bidsphysio.py"   '''

import bidsphysio.pmu2bidsphysio as p2bp
from .utils import TESTS_DATA_PATH

import pytest
import sys
from pathlib import Path

'''
TO-DO:

- Test main for the case of input argument a single file and
  for the case of a list

- Test readpmu:
    * Get also a VB15A sample file

- Test for testSamplingRate functions

- Set the expected signals (and maybe file contents) from the
  tests data in a separate file , with the data, which the test
  functions will read. That way, if we change the tests datasets,
  we will change the expected values right there, rather than
  changing the tests in this file
'''

###   Globals   ###

MSG = 'Test: %r'
PMUVE11CFILE = 'sample_VE11C.puls'
PMUVBXFILE = 'sample_VBX.puls'
EXPSTR = 'expected'
GOTSTR = 'foo'

# These are specific to the PMUVE11CFILE
STARTMDHTIME = 39008572
STOPMDHTIME = 39017760


###   Fixtures   ###

@pytest.fixture
def myErrmsg(scope="module"):
    '''   myErrmsg   '''
    return p2bp.errmsg(MSG, PMUVE11CFILE, EXPSTR, GOTSTR)


@pytest.fixture
def mock_pmu2bidsphysio(monkeypatch):
    """
    Pretend we run pmu2bids, but do nothing
    This allows us to test the correct behavior of the runner without
       actually running anything: just the instructions in the runner
       before the call to pmu2bids
    """
    def mock_pmu2bids(*args, **kwargs):
        print('mock_pmu2bids called')
        return

    monkeypatch.setattr(p2bp, "pmu2bids", mock_pmu2bids)



###   Tests   ###

def test_errmsg():
    '''
    Test that the message is what you expect, given the input args
    '''

    expectedMsg1 = "Test: '" + PMUVE11CFILE + "'"
    expectedMsg2 = expectedMsg1 + ": Expected: '" + EXPSTR + "'; got: '" + GOTSTR + "'"
    assert p2bp.errmsg(MSG, PMUVE11CFILE) == expectedMsg1
    assert p2bp.errmsg(MSG, PMUVE11CFILE, EXPSTR, GOTSTR) == expectedMsg2
    # NOTE: don't assert p2bp.errmsg(...) == myErrmsg, because here we're testing
    #       the output message formatting.


def test_PMUFormatError_class(myErrmsg):
    '''
    Test that when we create a new object of the class PMUFormatError, it
    gets initialized properly
    '''
    myError = p2bp.PMUFormatError(MSG, PMUVE11CFILE, EXPSTR, GOTSTR)
    assert isinstance(myError, p2bp.PMUFormatError)
    with pytest.raises(p2bp.PMUFormatError) as err_info:
        raise myError
        assert str(err_info.value) == myErrmsg


def test_parserawPMUsignal(capfd):
    '''
    Tests for parserawPMUsignal
    '''

    # 1) simulated raw signal without a '5003' value to indicate the end of the recording:
    raw_signal = ['', '1733', '1725', '1725', '1721', '1721', '1718']
    psignal = p2bp.parserawPMUsignal(raw_signal)
    assert capfd.readouterr().out.startswith('Warning: End of physio recording not found')
    assert float('NaN') not in psignal
    # make sure it returns all the values, except for the first empty one:
    assert psignal == [int(i) for i in raw_signal[1:]]

    # 2) simulated raw signal with '5003' and with '5000' and '6000', to indicate "trigger on" and "trigger off":
    raw_signal = ['1733', '5000', '1725', '6000', '1721', '5003', '1718']
    psignal = p2bp.parserawPMUsignal(raw_signal)
    assert 5000 not in psignal
    assert 6000 not in psignal
    assert psignal == pytest.approx([1733, float('NaN'), 1725, float('NaN'), 1721], nan_ok=True)


def test_getPMUtiming():
    '''
    Tests for getPMUtiming
    We only care about the lines that contain te MPCUTime and MDHTime
    '''

    # 1) If the keywords are missing, the outputs should be 0
    assert p2bp.getPMUtiming([]) == ([0,0], [0,0])
    
    # 1) If the keywords are present, we should get them back (as int)
    LogStartMPCUTime = 39009937
    LogStopMPCUTime = 39019125
    
    lines = [
        'LogStartMDHTime:  {0}'.format(STARTMDHTIME),
        'LogStopMDHTime:   {0}'.format(STOPMDHTIME),
        'LogStartMPCUTime: {0}'.format(LogStartMPCUTime),
        'LogStopMPCUTime:  {0}'.format(LogStopMPCUTime),
        '6003'
    ]

    assert p2bp.getPMUtiming(lines) == (
        [LogStartMPCUTime,LogStopMPCUTime],
        [STARTMDHTIME,STOPMDHTIME]
    )


def test_readVE11Cpmu():
    '''
    Tests for readVE11Cpmu
    '''

    # 1) If you test with a file with the wrong format, you should get a PMUFormatError
    with pytest.raises(p2bp.PMUFormatError) as err_info:
        physio_file = str(TESTS_DATA_PATH / PMUVBXFILE)
        p2bp.readVE11Cpmu(physio_file)
        assert str(err_info.value) == myErrmsg
    
    # 2) With the correct file format, you get the expected results:
    physio_file = str(TESTS_DATA_PATH / PMUVE11CFILE)

    physio_type, MDHTime, sampling_rate, physio_signal = p2bp.readVE11Cpmu(physio_file)
    assert physio_type == 'PULS'
    assert MDHTime == [STARTMDHTIME, STOPMDHTIME]
    assert sampling_rate == 400
    with open( TESTS_DATA_PATH / ('pmu_VE11C_pulse_sample.tsv'),'rt' ) as expected:
        for expected_line, returned_signal in zip (expected, physio_signal):
            assert float(expected_line) == returned_signal


def test_readVB15Apmu():
    '''
    Tests for readVB15Apmu
    '''

    # 1) If you test with a file with the wrong format, you should get a PMUFormatError
    with pytest.raises(p2bp.PMUFormatError) as err_info:
        physio_file = str(TESTS_DATA_PATH / PMUVBXFILE)
        p2bp.readVB15Apmu(physio_file)
        assert str(err_info.value) == myErrmsg
    '''
    # 2) With the correct file format, you get the expected results:
    physio_file = str(TESTS_DATA_PATH / PMUVE11CFILE)

    physio_type, MDHTime, sampling_rate, physio_signal = p2bp.readVB15Apmu(physio_file)
    assert physio_type == 'PULS'
    assert MDHTime == [STARTMDHTIME, STOPMDHTIME]
    assert sampling_rate == 400
    with open( TESTS_DATA_PATH / ('pmu_VB15A_pulse_sample.tsv'),'rt' ) as expected:
        for expected_line, returned_signal in zip (expected, physio_signal):
            assert float(expected_line) == returned_signal
    '''


def test_readVBXpmu():
    '''
    Tests for readVBXpmu
    '''

    # 1) If you test with a file with the wrong format, you should get a PMUFormatError
    with pytest.raises(p2bp.PMUFormatError) as err_info:
        physio_file = str(TESTS_DATA_PATH / PMUVE11CFILE)
        p2bp.readVBXpmu(physio_file)
        assert str(err_info.value) == myErrmsg
    
    # 2) With the correct file format, you get the expected results:
    physio_file = str(TESTS_DATA_PATH / PMUVBXFILE)

    physio_type, MDHTime, sampling_rate, physio_signal = p2bp.readVBXpmu(physio_file)
    assert physio_type == 'PULSE'
    assert MDHTime == [47029710, 47654452]
    assert sampling_rate == 50
    with open( TESTS_DATA_PATH / ('pmu_VBX_pulse_sample.tsv'),'rt' ) as expected:
        for expected_line, returned_signal in zip (expected, physio_signal):
            assert float(expected_line) == returned_signal


def test_main_args(
        monkeypatch,
        tmpdir,
        mock_pmu2bidsphysio,
        capfd
):
    '''
    Tests for "main"
    Just check the arguments, etc. We'll test the call to pmu2bids in a
    separated function
    '''
    # 1) "infile" doesn't exist:
    # Note: we enter "-i" last because in 3), we'll be adding a second file
    infile = str(tmpdir / 'boo.dcm')
    args = (
        'pmu2bidsphysio -b {bp} -i {infile}'.format(
            infile=infile,
            bp=tmpdir / 'mydir' / 'foo'
        )
    ).split(' ')
    monkeypatch.setattr(sys, 'argv',args)
    with pytest.raises(FileNotFoundError) as e_info:
        p2bp.main()
        assert str(e_info.value).endswith(' file not found')
        assert str(e_info.value).split(' file not found')[0] == infile

    # 2) "infile" does exist, but output directory doesn't exist:
    #    The output directory should be created and the "pmu2bids" function should be called
    args[ args.index('-i')+1 ] = str(TESTS_DATA_PATH / PMUVE11CFILE)
    monkeypatch.setattr(sys, 'argv',args)
    p2bp.main()
    assert (tmpdir / 'mydir').exists()
    assert capfd.readouterr().out == 'mock_pmu2bids called\n'

    # 3) "infile" contains more than one file:
    args.append(
        str(TESTS_DATA_PATH / PMUVBXFILE)
    )
    monkeypatch.setattr(sys, 'argv',args)
    # Make sure 'main' runs without errors:
    assert p2bp.main() is None


def test_testSamplingRate():
    '''   Tests for testSamplingRate   '''

    # 1) If the tolerance is wrong, we should get an error
    for t in [ -0.5, 5]:
        with pytest.raises(ValueError) as err_info:
            p2bp.testSamplingRate(tolerance=t)
            assert str(err_info.value) == 'tolerance has to be between 0 and 1. Got ' + str(t)

    # 2) If the sampling rate is incorrect (allowing for default tolerance),
    #    we should also get an error:
    #    Note that the logTimes are in ms, and the sampling rate in samples per sec
    with pytest.raises(ValueError) as err_info:
        p2bp.testSamplingRate(
            sampling_rate = 1,
            Nsamples = 100,
            logTimes = [0, 10000]
        )
        assert 'sampling rate' in str(err_info.value)

    # 3) If the sampling rate is correct (within the default tolerance),
    #    we should NOT get an error:
    assert p2bp.testSamplingRate(
        sampling_rate = 10,
        Nsamples = 99,
        logTimes = [0, 10000]
    ) is None