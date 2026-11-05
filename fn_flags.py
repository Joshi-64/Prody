"""Feature flags for Functionality's fn-features round. Flip DEMO_LABEL off when shipping for real."""
import os

# Shown on DMs + boards pages; set PRODY_DEMO_LABEL=0 to hide.
DEMO_LABEL = os.environ.get('PRODY_DEMO_LABEL', '0').lower() in ('1', 'true', 'yes', 'on')  # off by default for release
