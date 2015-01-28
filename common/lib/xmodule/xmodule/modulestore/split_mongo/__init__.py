"""
General utilities
"""

from collections import namedtuple
from contracts import contract, check
from opaque_keys.edx.locator import BlockUsageLocator


class BlockKey(namedtuple('BlockKey', 'type id')):
    __slots__ = ()

    @contract(type="string[>0]")
    def __new__(cls, type, id):
        return super(BlockKey, cls).__new__(cls, type, id)

    @classmethod
    @contract(usage_key=BlockUsageLocator)
    def from_usage_key(cls, usage_key):
        return cls(usage_key.block_type, usage_key.block_id)


CourseEnvelope = namedtuple('CourseEnvelope', 'course_key structure')


class EditInfo(object):
    """
    Encapsulates the editing info of a block.
    """
    __slots__ = (
        'previous_version',
        'update_version',
        'source_version',
        'edited_on',
        'edited_by',
        'original_usage',
        'original_usage_version',
        '_subtree_edited_on',
        '_subtree_edited_by',
    )

    def __init__(self, edit_info={}):  # pylint: disable=dangerous-default-value
        self.from_storable(edit_info)

        # Used by Split.
        self.original_usage = None
        self.original_usage_version = None

        # For details, see caching_descriptor_system.py get_subtree_edited_by/on.
        self._subtree_edited_on = None
        self._subtree_edited_by = None

    def to_storable(self):
        """
        Serialize to a Mongo-storable format.
        """
        return {
            'previous_version': self.previous_version,
            'update_version': self.update_version,
            'source_version': self.source_version,
            'edited_on': self.edited_on,
            'edited_by': self.edited_by,
        }

    def from_storable(self, edit_info):
        """
        De-serialize from Mongo-storable format to an object.
        """
        self.previous_version = edit_info.get('previous_version', None)
        self.update_version = edit_info.get('update_version', None)
        self.source_version = edit_info.get('source_version', None)
        self.edited_on = edit_info.get('edited_on', None)
        self.edited_by = edit_info.get('edited_by', None)

    def __str__(self):
        return ("EditInfo(previous_version={self.previous_version}, "
                        "update_version={self.update_version}, "
                        "source_version={self.source_version}, "
                        "edited_on={self.edited_on}, "
                        "edited_by={self.edited_by}, "
                        "original_usage={self.original_usage}, "
                        "original_usage_version={self.original_usage_version}, "
                        "_subtree_edited_on={self._subtree_edited_on}, "
                        "_subtree_edited_by={self._subtree_edited_by})").format(self=self)


class BlockData(object):
    """
    Wrap the block data in an object instead of using a straight Python dictionary.
    Allows the storing of meta-information about a structure that doesn't persist along with
    the structure itself.
    """
    __slots__ = (
        'fields',
        'block_type',
        'definition',
        'defaults',
        'edit_info',
        'definition_loaded'
    )

    @contract(block_dict=dict)
    def __init__(self, block_dict={}):  # pylint: disable=dangerous-default-value
        # Has the definition been loaded?
        self.definition_loaded = False
        self.from_storable(block_dict)

    def to_storable(self):
        """
        Serialize to a Mongo-storable format.
        """
        return {
            'fields': self.fields,
            'block_type': self.block_type,
            'definition': self.definition,
            'defaults': self.defaults,
            'edit_info': self.edit_info.to_storable()
        }

    @contract(stored=dict)
    def from_storable(self, stored):
        """
        De-serialize from Mongo-storable format to an object.
        """
        self.fields = stored.get('fields', {})
        self.block_type = stored.get('block_type', None)
        self.definition = stored.get('definition', None)
        self.defaults = stored.get('defaults', {})
        self.edit_info = EditInfo(stored.get('edit_info', {}))

    def __str__(self):
        return ("BlockData(fields={self.fields}, "
                         "block_type={self.block_type}, "
                         "definition={self.definition}, "
                         "definition_loaded={self.definition_loaded}, "
                         "defaults={self.defaults}, "
                         "edit_info={self.edit_info})").format(self=self)

    def __contains__(self, item):
        return item in self.__slots__

    def __getitem__(self, key):
        """
        Dict-like '__getitem__'.
        """
        if not hasattr(self, key):
            raise KeyError
        else:
            return getattr(self, key)
