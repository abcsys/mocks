import digi
import digi.on as on

import digi.util as util
import inflection

def gvr(kind):
    return f"mock.digi.dev/v1/{inflection.pluralize(kind)}"

