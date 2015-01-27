"""
Utilities for tests within the django_comment_client module.
"""
from datetime import datetime
from django.test.utils import override_settings
from mock import patch
from pytz import UTC

from openedx.core.djangoapps.course_groups.models import CourseUserGroupPartitionGroup
from openedx.core.djangoapps.course_groups.tests.helpers import CohortFactory
from xmodule.modulestore.tests.django_utils import TEST_DATA_MOCK_MODULESTORE
from django_comment_common.models import Role
from django_comment_common.utils import seed_permissions_roles
from student.tests.factories import CourseEnrollmentFactory, UserFactory
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.partitions.partitions import UserPartition, Group


@override_settings(MODULESTORE=TEST_DATA_MOCK_MODULESTORE)
class CohortedTestCase(ModuleStoreTestCase):
    """
    Sets up a course with a student, a moderator and their cohorts.
    """
    @patch.dict("django.conf.settings.FEATURES", {"ENABLE_DISCUSSION_SERVICE": True})
    def setUp(self):
        super(CohortedTestCase, self).setUp()

        self.course = CourseFactory.create(
            discussion_topics={
                "cohorted topic": {"id": "cohorted_topic"},
                "non-cohorted topic": {"id": "non_cohorted_topic"},
            },
            cohort_config={
                "cohorted": True,
                "cohorted_discussions": ["cohorted_topic"]
            }
        )
        self.student_cohort = CohortFactory.create(
            name="student_cohort",
            course_id=self.course.id
        )
        self.moderator_cohort = CohortFactory.create(
            name="moderator_cohort",
            course_id=self.course.id
        )

        seed_permissions_roles(self.course.id)
        self.student = UserFactory.create()
        self.moderator = UserFactory.create()
        CourseEnrollmentFactory(user=self.student, course_id=self.course.id)
        CourseEnrollmentFactory(user=self.moderator, course_id=self.course.id)
        self.moderator.roles.add(Role.objects.get(name="Moderator", course_id=self.course.id))
        self.student_cohort.users.add(self.student)
        self.moderator_cohort.users.add(self.moderator)


@override_settings(MODULESTORE=TEST_DATA_MOCK_MODULESTORE)
class ContentGroupTestCase(ModuleStoreTestCase):
    """
    Sets up a discussion module visible to a content group 'alpha'.
    Creates a staff user, a user in alpha (by way of a cohort), and a
    user in a separate content group 'beta'.
    """
    def setUp(self):
        super(ContentGroupTestCase, self).setUp()

        self.staff_user = UserFactory.create(is_staff=True)
        self.alpha_user = UserFactory.create()
        self.beta_user = UserFactory.create()
        self.course = CourseFactory.create(
            # This test needs to use a course that has already started --
            # discussion topics only show up if the course has already started,
            # and the default start date for courses is Jan 1, 2030.
            start=datetime(2012, 2, 3, tzinfo=UTC),
            user_partitions=[
                UserPartition(
                    0,
                    'Content Group Configuration',
                    '',
                    [Group(1, 'Alpha'), Group(2, 'Beta')],
                    scheme_id='cohort'
                )
            ],
            cohort_config={'cohorted': True},
            discussion_topics={}
        )
        alpha_cohort = CohortFactory(
            course_id=self.course.id,
            name='Cohort Alpha',
            users=[self.alpha_user]
        )
        beta_cohort = CohortFactory(
            course_id=self.course.id,
            name='Cohort Beta',
            users=[self.beta_user]
        )
        CourseUserGroupPartitionGroup.objects.create(
            course_user_group=alpha_cohort,
            partition_id=self.course.user_partitions[0].id,
            group_id=self.course.user_partitions[0].groups[0].id
        )
        CourseUserGroupPartitionGroup.objects.create(
            course_user_group=beta_cohort,
            partition_id=self.course.user_partitions[0].id,
            group_id=self.course.user_partitions[0].groups[1].id
        )
        ItemFactory.create(
            parent_location=self.course.location,
            category='discussion',
            discussion_id='content_group_discussion',
            discussion_target='Visible to Alpha',
            group_access={self.course.user_partitions[0].id: [self.course.user_partitions[0].groups[0].id]}
        )
