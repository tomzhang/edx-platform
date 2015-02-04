""" Permissions classes utilized by Django REST Framework """
import logging

from django.conf import settings

from rest_framework import permissions, generics, filters, pagination, serializers
from rest_framework.views import APIView

from server_api.models import APIUser as User
from server_api.util.utils import get_client_ip_address, address_exists_in_network, str2bool

log = logging.getLogger(__name__)


class ApiKeyHeaderPermission(permissions.BasePermission):
    """
    Check for permissions by matching the configured API key and header

    """
    def has_permission(self, request, view):
        """
        If settings.DEBUG is True and settings.EDX_API_KEY is not set or None,
        then allow the request. Otherwise, allow the request if and only if
        settings.EDX_API_KEY is set and the X-Edx-Api-Key HTTP header is
        present in the request and matches the setting.
        """

        debug_enabled = settings.DEBUG
        api_key = getattr(settings, "EDX_API_KEY", None)

        # DEBUG mode rules over all else
        # Including the api_key check here ensures we don't break the feature locally
        if debug_enabled and api_key is None:
            log.warn("EDX_API_KEY Override: Debug Mode")
            return True

        # If we're not DEBUG, we need a local api key
        if api_key is None:
            return False

        # The client needs to present the same api key
        header_key = request.META.get('HTTP_X_EDX_API_KEY')
        if header_key is None:
            try:
                header_key = request.META['headers'].get('X-Edx-Api-Key')
            except KeyError:
                return False
            if header_key is None:
                return False

        # The api key values need to be the same
        if header_key != api_key:
            return False

        # Allow the request to take place
        return True


class IPAddressRestrictedPermission(permissions.BasePermission):
    """
    Check for permissions by matching the request IP address
    against the allowed ip address(s)
    """

    def has_permission(self, request, view):
        ip_address = get_client_ip_address(request)
        allowed_ip_addresses = getattr(settings, 'API_ALLOWED_IP_ADDRESSES', None)
        if allowed_ip_addresses:
            for allowed_ip_address in allowed_ip_addresses:
                if '/' in allowed_ip_address:
                    is_allowed = address_exists_in_network(ip_address, allowed_ip_address)
                    if is_allowed:
                        return is_allowed
                else:
                    if ip_address == allowed_ip_address:
                        return True
            log.warn("{} is not allowed to access Api".format(ip_address))
            return False
        else:
            return True


class IdsInFilterBackend(filters.BaseFilterBackend):
    """
        This backend support filtering queryset by a list of ids
    """
    def filter_queryset(self, request, queryset, view):
        """
        Parse querystring to get ids and the filter the queryset
        Max of 800 values are allowed for performance reasons
        (800 satisfies a specific client integration use case)
        """
        upper_bound = getattr(settings, 'API_LOOKUP_UPPER_BOUND', 800)
        ids = request.QUERY_PARAMS.get('ids')
        if ids:
            ids = ids.split(",")[:upper_bound]
            return queryset.filter(id__in=ids)
        return queryset


class HasOrgsFilterBackend(filters.BaseFilterBackend):
    """
        This backend support filtering users with and organization association or not
    """
    def filter_queryset(self, request, queryset, view):
        """
        Parse querystring base on has_organizations query param
        """
        has_orgs = request.QUERY_PARAMS.get('has_organizations', None)
        if has_orgs:
            if str2bool(has_orgs):
                queryset = queryset.filter(organizations__id__gt=0)
            else:
                queryset = queryset.exclude(id__in=User.objects.filter(organizations__id__gt=0).
                                            values_list('id', flat=True))
        return queryset.distinct()


class CustomPaginationSerializer(pagination.PaginationSerializer):
    """
    Custom PaginationSerializer to include num_pages field
    """
    num_pages = serializers.Field(source='paginator.num_pages')


class SecureAPIView(APIView):
    """
    View used for protecting access to specific workflows
    """
    permission_classes = (ApiKeyHeaderPermission, )


class PermissionMixin(object):
    """
    Mixin to set custom permission_classes
    """
    permission_classes = (ApiKeyHeaderPermission, IPAddressRestrictedPermission)


class FilterBackendMixin(object):
    """
    Mixin to set custom filter_backends
    """
    filter_backends = (filters.DjangoFilterBackend, IdsInFilterBackend,)


class PaginationMixin(object):
    """
    Mixin to set custom pagination support
    """
    pagination_serializer_class = CustomPaginationSerializer
    paginate_by = getattr(settings, 'API_PAGE_SIZE', 20)
    paginate_by_param = 'page_size'
    max_paginate_by = 150


class SecureListAPIView(PermissionMixin,
                        FilterBackendMixin,
                        PaginationMixin,
                        generics.ListAPIView):
    """
        Inherited from ListAPIView
    """
    pass
