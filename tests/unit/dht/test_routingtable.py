import hashlib
from binascii import hexlify, unhexlify

from twisted.trial import unittest
from twisted.internet import defer
from lbrynet.dht import constants
from lbrynet.dht.routingtable import TreeRoutingTable
from lbrynet.dht.contact import ContactManager
from lbrynet.dht.distance import Distance
import sys
if sys.version_info > (3,):
    long = int


class FakeRPCProtocol(object):
    """ Fake RPC protocol; allows lbrynet.dht.contact.Contact objects to "send" RPCs """
    def sendRPC(self, *args, **kwargs):
        return defer.succeed(None)


class TreeRoutingTableTest(unittest.TestCase):
    """ Test case for the RoutingTable class """
    def setUp(self):
        h = hashlib.sha384()
        h.update(b'node1')
        self.contact_manager = ContactManager()
        self.nodeID = h.digest()
        self.protocol = FakeRPCProtocol()
        self.routingTable = TreeRoutingTable(self.nodeID)

    def testDistance(self):
        """ Test to see if distance method returns correct result"""

        # testList holds a couple 3-tuple (variable1, variable2, result)
        basicTestList = [(bytes(b'\xaa' * 48), bytes(b'\x55' * 48), long(hexlify(bytes(b'\xff' * 48)), 16))]

        for test in basicTestList:
            result = Distance(test[0])(test[1])
            self.assertFalse(result != test[2], 'Result of _distance() should be %s but %s returned' %
                        (test[2], result))

    @defer.inlineCallbacks
    def testAddContact(self):
        """ Tests if a contact can be added and retrieved correctly """
        # Create the contact
        h = hashlib.sha384()
        h.update(b'node2')
        contactID = h.digest()
        contact = self.contact_manager.make_contact(contactID, '127.0.0.1', 9182, self.protocol)
        # Now add it...
        yield self.routingTable.addContact(contact)
        # ...and request the closest nodes to it (will retrieve it)
        closestNodes = self.routingTable.findCloseNodes(contactID)
        self.assertEqual(len(closestNodes), 1, 'Wrong amount of contacts returned; expected 1,'
                                                   ' got %d' % len(closestNodes))
        self.assertTrue(contact in closestNodes, 'Added contact not found by issueing '
                                                 '_findCloseNodes()')

    @defer.inlineCallbacks
    def testGetContact(self):
        """ Tests if a specific existing contact can be retrieved correctly """
        h = hashlib.sha384()
        h.update(b'node2')
        contactID = h.digest()
        contact = self.contact_manager.make_contact(contactID, '127.0.0.1', 9182, self.protocol)
        # Now add it...
        yield self.routingTable.addContact(contact)
        # ...and get it again
        sameContact = self.routingTable.getContact(contactID)
        self.assertEqual(contact, sameContact, 'getContact() should return the same contact')

    @defer.inlineCallbacks
    def testAddParentNodeAsContact(self):
        """
        Tests the routing table's behaviour when attempting to add its parent node as a contact
        """

        # Create a contact with the same ID as the local node's ID
        contact = self.contact_manager.make_contact(self.nodeID, '127.0.0.1', 9182, self.protocol)
        # Now try to add it
        yield self.routingTable.addContact(contact)
        # ...and request the closest nodes to it using FIND_NODE
        closestNodes = self.routingTable.findCloseNodes(self.nodeID, constants.k)
        self.assertFalse(contact in closestNodes, 'Node added itself as a contact')

    @defer.inlineCallbacks
    def testRemoveContact(self):
        """ Tests contact removal """
        # Create the contact
        h = hashlib.sha384()
        h.update(b'node2')
        contactID = h.digest()
        contact = self.contact_manager.make_contact(contactID, '127.0.0.1', 9182, self.protocol)
        # Now add it...
        yield self.routingTable.addContact(contact)
        # Verify addition
        self.assertEqual(len(self.routingTable._buckets[0]), 1, 'Contact not added properly')
        # Now remove it
        self.routingTable.removeContact(contact)
        self.assertEqual(len(self.routingTable._buckets[0]), 0, 'Contact not removed properly')

    @defer.inlineCallbacks
    def testSplitBucket(self):
        """ Tests if the the routing table correctly dynamically splits k-buckets """
        self.assertEqual(self.routingTable._buckets[0].rangeMax, 2**384,
                             'Initial k-bucket range should be 0 <= range < 2**384')
        # Add k contacts
        for i in range(constants.k):
            h = hashlib.sha384()
            h.update(b'remote node %d' % i)
            nodeID = h.digest()
            contact = self.contact_manager.make_contact(nodeID, '127.0.0.1', 9182, self.protocol)
            yield self.routingTable.addContact(contact)
        self.assertEqual(len(self.routingTable._buckets), 1,
                             'Only k nodes have been added; the first k-bucket should now '
                             'be full, but should not yet be split')
        # Now add 1 more contact
        h = hashlib.sha384()
        h.update(b'yet another remote node')
        nodeID = h.digest()
        contact = self.contact_manager.make_contact(nodeID, '127.0.0.1', 9182, self.protocol)
        yield self.routingTable.addContact(contact)
        self.assertEqual(len(self.routingTable._buckets), 2,
                             'k+1 nodes have been added; the first k-bucket should have been '
                             'split into two new buckets')
        self.assertNotEqual(self.routingTable._buckets[0].rangeMax, 2**384,
                         'K-bucket was split, but its range was not properly adjusted')
        self.assertEqual(self.routingTable._buckets[1].rangeMax, 2**384,
                             'K-bucket was split, but the second (new) bucket\'s '
                             'max range was not set properly')
        self.assertEqual(self.routingTable._buckets[0].rangeMax,
                             self.routingTable._buckets[1].rangeMin,
                             'K-bucket was split, but the min/max ranges were '
                             'not divided properly')

    @defer.inlineCallbacks
    def testFullSplit(self):
        """
        Test that a bucket is not split if it is full, but the new contact is not closer than the kth closest contact
        """

        self.routingTable._parentNodeID = bytes(48 * b'\xff')

        node_ids = [
            b"100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            b"200000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            b"300000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            b"400000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            b"500000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            b"600000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            b"700000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            b"800000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            b"ff0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
            b"010000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        ]

        # Add k contacts
        for nodeID in node_ids:
            # self.assertEquals(nodeID, node_ids[i].decode('hex'))
            contact = self.contact_manager.make_contact(unhexlify(nodeID), '127.0.0.1', 9182, self.protocol)
            yield self.routingTable.addContact(contact)
        self.assertEqual(len(self.routingTable._buckets), 2)
        self.assertEqual(len(self.routingTable._buckets[0]._contacts), 8)
        self.assertEqual(len(self.routingTable._buckets[1]._contacts), 2)

        #  try adding a contact who is further from us than the k'th known contact
        nodeID = b'020000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        nodeID = unhexlify(nodeID)
        contact = self.contact_manager.make_contact(nodeID, '127.0.0.1', 9182, self.protocol)
        self.assertFalse(self.routingTable._shouldSplit(self.routingTable._kbucketIndex(contact.id), contact.id))
        yield self.routingTable.addContact(contact)
        self.assertEqual(len(self.routingTable._buckets), 2)
        self.assertEqual(len(self.routingTable._buckets[0]._contacts), 8)
        self.assertEqual(len(self.routingTable._buckets[1]._contacts), 2)
        self.assertFalse(contact in self.routingTable._buckets[0]._contacts)
        self.assertFalse(contact in self.routingTable._buckets[1]._contacts)


# class KeyErrorFixedTest(unittest.TestCase):
#     """ Basic tests case for boolean operators on the Contact class """
#
#     def setUp(self):
#         own_id = (2 ** constants.key_bits) - 1
#         # carefully chosen own_id. here's the logic
#         # we want a bunch of buckets (k+1, to be exact), and we want to make sure own_id
#         # is not in bucket 0. so we put own_id at the end so we can keep splitting by adding to the
#         # end
#
#         self.table = lbrynet.dht.routingtable.OptimizedTreeRoutingTable(own_id)
#
#     def fill_bucket(self, bucket_min):
#         bucket_size = lbrynet.dht.constants.k
#         for i in range(bucket_min, bucket_min + bucket_size):
#             self.table.addContact(lbrynet.dht.contact.Contact(long(i), '127.0.0.1', 9999, None))
#
#     def overflow_bucket(self, bucket_min):
#         bucket_size = lbrynet.dht.constants.k
#         self.fill_bucket(bucket_min)
#         self.table.addContact(
#             lbrynet.dht.contact.Contact(long(bucket_min + bucket_size + 1),
#                                         '127.0.0.1', 9999, None))
#
#     def testKeyError(self):
#
#         # find middle, so we know where bucket will split
#         bucket_middle = self.table._buckets[0].rangeMax / 2
#
#         # fill last bucket
#         self.fill_bucket(self.table._buckets[0].rangeMax - lbrynet.dht.constants.k - 1)
#         # -1 in previous line because own_id is in last bucket
#
#         # fill/overflow 7 more buckets
#         bucket_start = 0
#         for i in range(0, lbrynet.dht.constants.k):
#             self.overflow_bucket(bucket_start)
#             bucket_start += bucket_middle / (2 ** i)
#
#         # replacement cache now has k-1 entries.
#         # adding one more contact to bucket 0 used to cause a KeyError, but it should work
#         self.table.addContact(
#             lbrynet.dht.contact.Contact(long(lbrynet.dht.constants.k + 2), '127.0.0.1', 9999, None))
#
#         # import math
#         # print ""
#         # for i, bucket in enumerate(self.table._buckets):
#         #     print "Bucket " + str(i) + " (2 ** " + str(
#         #         math.log(bucket.rangeMin, 2) if bucket.rangeMin > 0 else 0) + " <= x < 2 ** "+str(
#         #         math.log(bucket.rangeMax, 2)) + ")"
#         #     for c in bucket.getContacts():
#         #         print "  contact " + str(c.id)
#         # for key, bucket in self.table._replacementCache.items():
#         #     print "Replacement Cache for Bucket " + str(key)
#         #     for c in bucket:
#         #         print "  contact " + str(c.id)