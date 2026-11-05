"""Calendar sync entry renders for a fresh account with no events."""
from _jobs_helpers import client_for, make_user


def test_sync_button_renders_with_no_events():
    html = client_for(make_user()).get('/calendar').get_data(as_text=True)
    assert 'id="ctSyncBtn"' in html and 'Sync Google / iCollege' in html
    assert "openModal('importModal')" in html and 'id="importModal"' in html
    assert 'Where do I find my .ics link?' in html
    assert 'Secret address in iCal format' in html
