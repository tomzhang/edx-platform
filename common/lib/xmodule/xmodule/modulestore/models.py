import copy


class EqualityMixin(object):
    def __eq__(self, other):
        return isinstance(other, self.__class__) and (self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not self.__eq__(other)


class Block(EqualityMixin):
    """
    Represents a course block/tree node.
    """

    def __init__(self, id, type, display_name=None, format=None, graded=False, children=None):
        self.id = id
        self.type = type
        self.children = children or []
        self.display_name = display_name
        self.format = format
        self.graded = graded

    def __unicode__(self):
        return self.display_name

    def __str__(self):
        return unicode(self).encode('utf-8')

    @classmethod
    def from_dict(cls, d):
        """
        Converts a dictionary to a Block object.

        The dictionary MUST have the following format:

        {
            u'id': u'block-v1:edX+DemoX+2014_T1+type@sequential+block@basic_questions'
            u'block_type': u'sequential',
            u'children': [u'block-v1:edX+DemoX+2014_T1+type@vertical+block@2152d4a4aadc4cb0af5256394a3d1fc7',
                         u'block-v1:edX+DemoX+2014_T1+type@vertical+block@47dbd5f836544e61877a483c0b75606c',
                         ...],
           u'display_name': u'Homework - Question Styles',
           u'format': u'Homework',
           u'graded': True
       }
        """
        return cls(d[u'id'], d[u'block_type'], d[u'display_name'], d[u'format'], d[u'graded'], d[u'children'])


class CourseStructure(EqualityMixin):
    """
    Representation of a course's tree structure.
    """

    def __init__(self, root, blocks):
        self.root = root
        self.blocks = copy.deepcopy(blocks)

    @classmethod
    def from_dict(cls, d):
        """
        Converts a dictionary to a CourseStructure object.

        The dictionary MUST have the following format:
        {
            u'root': u'block-v1:edX+DemoX+2014_T1+type@course+block@course',
            u'blocks': {
                u'block-v1:edX+DemoX+2014_T1+type@sequential+block@basic_questions': {
                    u'block_type': u'sequential',
                    u'children': [u'block-v1:edX+DemoX+2014_T1+type@vertical+block@2152d4a4aadc4cb0af5256394a3d1fc7',
                                 u'block-v1:edX+DemoX+2014_T1+type@vertical+block@47dbd5f836544e61877a483c0b75606c',
                                 ...],
                   u'display_name': u'Homework - Question Styles',
                   u'format': u'Homework',
                   u'graded': True
               },
               ...
            }
        }
        :param d: Dictionary to be converted
        :return: CourseStructure object
        """
        blocks = {}
        for key, block in d[u'blocks'].iteritems():
            blocks[key] = Block.from_dict(block)

        structure = cls(d[u'root'], blocks)

        return structure
