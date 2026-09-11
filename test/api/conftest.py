import nccrd.api
from nccrd.api.lib.auth import create_access_token
from nccrd.db.models.rbac import User
from test.factories import FactorySession

from starlette.testclient import TestClient
import pytest


@pytest.fixture
def api():
    """Fixture returning an API test client constructor, authenticated as a
    real user via a real JWT (mirrors what the frontend sends). Example::

        r = api(permissions=['create-submission']).post('/submission/', json={...})

    :param permissions: iterable of permission names to grant the test user,
        via a freshly-created role assigned on the default tenant. Pass an
        empty list (the default) for an authenticated user with no
        permissions, to test 403s.
    """

    def api_test_client(*, email: str = 'test.user@example.org', name: str = 'Test User', permissions=()):
        from nccrd.db.models.rbac import Permission, PermissionXrefRole, Role, Tenant, UserXrefRoleXrefTenant

        user = User(name=name, email=email)
        FactorySession.add(user)
        FactorySession.commit()

        if permissions:
            tenant = FactorySession.query(Tenant).filter(Tenant.is_default.is_(True)).first()
            if tenant is None:
                tenant = Tenant(hostname='test.nccrd.localhost', title='Test Tenant', is_default=True)
                FactorySession.add(tenant)
                FactorySession.commit()

            role = Role(name=f'test-role-{user.id}')
            FactorySession.add(role)
            FactorySession.commit()

            for permission_name in permissions:
                permission = FactorySession.query(Permission).filter(Permission.name == permission_name).first()
                if permission is None:
                    permission = Permission(name=permission_name)
                    FactorySession.add(permission)
                    FactorySession.commit()
                FactorySession.add(PermissionXrefRole(permission_id=permission.id, role_id=role.id))

            FactorySession.add(UserXrefRoleXrefTenant(user_id=user.id, role_id=role.id, tenant_id=tenant.id))
            FactorySession.commit()

        token = create_access_token(user)

        return TestClient(
            app=nccrd.api.app,
            headers={
                'Accept': 'application/json',
                'Authorization': f'Bearer {token}',
                'Host': 'test.nccrd.localhost',
            },
        )

    return api_test_client
