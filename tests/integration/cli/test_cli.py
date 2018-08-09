import os
import signal
import asyncio
import sys
import time
import logging
# import unittest

# import twisted
# twisted.internet.base.DelayedCall.debug = True


from twisted.internet import defer, threads
from twisted.trial import unittest

from lbrynet import conf
from lbrynet import cli
from lbrynet.daemon.Components import DATABASE_COMPONENT, BLOB_COMPONENT, HEADERS_COMPONENT, WALLET_COMPONENT, \
    DHT_COMPONENT, HASH_ANNOUNCER_COMPONENT, STREAM_IDENTIFIER_COMPONENT, FILE_MANAGER_COMPONENT, \
    PEER_PROTOCOL_SERVER_COMPONENT, REFLECTOR_COMPONENT, UPNP_COMPONENT, EXCHANGE_RATE_MANAGER_COMPONENT, \
    RATE_LIMITER_COMPONENT, PAYMENT_RATE_COMPONENT
from lbrynet.daemon.Daemon import Daemon
from lbrynet.daemon.DaemonControl import start as d_start


root = logging.getLogger()
ch = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)


def f2d(c):
    return defer.Deferred.fromFuture(asyncio.ensure_future(c))


class CLIIntegrationTest(unittest.TestCase):
    def setUp(self):
        logging.getLogger('lbrynet.daemon').setLevel(logging.DEBUG)

        skip = [
            DATABASE_COMPONENT, BLOB_COMPONENT, HEADERS_COMPONENT, WALLET_COMPONENT,
            DHT_COMPONENT, HASH_ANNOUNCER_COMPONENT, STREAM_IDENTIFIER_COMPONENT, FILE_MANAGER_COMPONENT,
            PEER_PROTOCOL_SERVER_COMPONENT, REFLECTOR_COMPONENT, UPNP_COMPONENT, EXCHANGE_RATE_MANAGER_COMPONENT,
            RATE_LIMITER_COMPONENT, PAYMENT_RATE_COMPONENT
        ]
        conf.initialize_settings(load_conf_file=False)
        conf.settings['use_auth_http'] = True
        conf.settings["components_to_skip"] = skip
        conf.settings.initialize_post_conf_load()
        Daemon.component_attributes = {}
        self.daemon = Daemon()

    def test_cli_starts_with_auth(self):
        pid = os.fork()
        if not pid:
            # from twisted.internet import reactor
            # Daemon().start_listening()
            # reactor.run()
            with self.assertRaises(SystemExit):
                sys.exit(d_start(["--http-auth"]))
            # sys.exit(0)

        time.sleep(6)
        cli.main(["status"])
        cli.main(["stop"])
        os.kill(pid, 15)

    @defer.inlineCallbacks
    def test_cli_starts_with_auth_2(self):
        yield self.daemon.start_listening()
        yield f2d(cli.execute_command("status", []))
        yield self.daemon.jsonrpc_stop()
        print("here")