"""User directory behind the User access screen.

Production: Amazon Cognito (users = accounts, groups = workspace roles and permissions).
Development and tests (MERIDIAN_AUTH=dev): a local table in the app database, same interface.

All access rules live in `AccessAdmin` (main.py calls it); this module only reads and writes the directory.
"""
from __future__ import annotations

import os
from functools import lru_cache

from fastapi import HTTPException

from . import auth


def _norm_roles(roles) -> list[str]:
    out = []
    for r in roles or []:
        if r not in auth.ROLES:
            raise HTTPException(400, f"Unknown role or permission: {r}")
        if r not in out:
            out.append(r)
    return out


class CognitoDirectory:
    def __init__(self, pool_id: str, region: str):
        import boto3
        self.pool, self.c = pool_id, boto3.client("cognito-idp", region_name=region)

    def _attrs(self, u: dict) -> dict:
        return {a["Name"]: a["Value"] for a in u.get("Attributes", u.get("UserAttributes", []))}

    def _find(self, email: str) -> dict | None:
        r = self.c.list_users(UserPoolId=self.pool, Filter=f'email = "{email}"', Limit=2)
        return r["Users"][0] if r["Users"] else None

    def _username(self, email: str) -> str:
        u = self._find(email)
        if not u:
            raise HTTPException(404, f"No user {email}")
        return u["Username"]

    def list_users(self) -> list[dict]:
        users, token = {}, None
        while True:
            kw = {"UserPoolId": self.pool, "Limit": 60} | ({"PaginationToken": token} if token else {})
            r = self.c.list_users(**kw)
            for u in r["Users"]:
                a = self._attrs(u)
                users[u["Username"]] = {"email": a.get("email", ""), "name": a.get("name", ""), "roles": [],
                                        "enabled": u["Enabled"], "status": u["UserStatus"],
                                        "created": u["UserCreateDate"].isoformat()}
            token = r.get("PaginationToken")
            if not token:
                break
        for g in auth.ROLES:
            token = None
            while True:
                kw = {"UserPoolId": self.pool, "GroupName": g, "Limit": 60} | ({"NextToken": token} if token else {})
                try:
                    r = self.c.list_users_in_group(**kw)
                except self.c.exceptions.ResourceNotFoundException:
                    break
                for u in r["Users"]:
                    if u["Username"] in users:
                        users[u["Username"]]["roles"].append(g)
                token = r.get("NextToken")
                if not token:
                    break
        return sorted(users.values(), key=lambda x: (x["name"] or x["email"]).lower())

    def get(self, email: str) -> dict:
        u = self._find(email)
        if not u:
            raise HTTPException(404, f"No user {email}")
        a = self._attrs(u)
        groups = self.c.admin_list_groups_for_user(UserPoolId=self.pool, Username=u["Username"])["Groups"]
        return {"email": a.get("email", ""), "name": a.get("name", ""), "enabled": u["Enabled"],
                "status": u["UserStatus"], "created": u["UserCreateDate"].isoformat(),
                "roles": [g["GroupName"] for g in groups if g["GroupName"] in auth.ROLES]}

    def create(self, email: str, name: str, roles: list[str]) -> None:
        if self._find(email):
            raise HTTPException(409, f"{email} already has an account")
        self.c.admin_create_user(UserPoolId=self.pool, Username=email, DesiredDeliveryMediums=["EMAIL"],
                                 UserAttributes=[{"Name": "email", "Value": email},
                                                 {"Name": "email_verified", "Value": "true"},
                                                 {"Name": "name", "Value": name}])
        self.set_roles(email, roles)

    def set_roles(self, email: str, roles: list[str]) -> None:
        uname = self._username(email)
        have = {g["GroupName"] for g in self.c.admin_list_groups_for_user(UserPoolId=self.pool, Username=uname)["Groups"]}
        want = set(roles)
        for g in want - have:
            self.c.admin_add_user_to_group(UserPoolId=self.pool, Username=uname, GroupName=g)
        for g in (have - want) & set(auth.ROLES):
            self.c.admin_remove_user_from_group(UserPoolId=self.pool, Username=uname, GroupName=g)

    def rename(self, email: str, name: str) -> None:
        self.c.admin_update_user_attributes(UserPoolId=self.pool, Username=self._username(email),
                                            UserAttributes=[{"Name": "name", "Value": name}])

    def set_enabled(self, email: str, enabled: bool) -> None:
        uname = self._username(email)
        if enabled:
            self.c.admin_enable_user(UserPoolId=self.pool, Username=uname)
        else:
            self.c.admin_disable_user(UserPoolId=self.pool, Username=uname)
            self.c.admin_user_global_sign_out(UserPoolId=self.pool, Username=uname)

    def resend_invite(self, email: str) -> None:
        self.c.admin_create_user(UserPoolId=self.pool, Username=email, MessageAction="RESEND",
                                 DesiredDeliveryMediums=["EMAIL"])

    def delete(self, email: str) -> None:
        self.c.admin_delete_user(UserPoolId=self.pool, Username=self._username(email))


class LocalDirectory:
    """Same interface, backed by the app database (development and automated tests only)."""

    def __init__(self, store):
        self.st = store

    def _row(self, s, email):
        from .store import DevUser
        u = s.get(DevUser, email.lower())
        if not u:
            raise HTTPException(404, f"No user {email}")
        return u

    def list_users(self) -> list[dict]:
        from sqlalchemy import select

        from .store import DevUser
        with self.st.Session() as s:
            return sorted(({"email": u.email, "name": u.name, "roles": list(u.roles), "enabled": u.enabled,
                            "status": u.status, "created": u.created.isoformat()}
                           for u in s.execute(select(DevUser)).scalars()), key=lambda x: x["name"].lower())

    def get(self, email: str) -> dict:
        with self.st.Session() as s:
            u = self._row(s, email)
            return {"email": u.email, "name": u.name, "roles": list(u.roles), "enabled": u.enabled,
                    "status": u.status, "created": u.created.isoformat()}

    def create(self, email: str, name: str, roles: list[str]) -> None:
        from .store import DevUser
        with self.st.Session.begin() as s:
            if s.get(DevUser, email.lower()):
                raise HTTPException(409, f"{email} already has an account")
            s.add(DevUser(email=email.lower(), name=name, roles=list(roles)))

    def set_roles(self, email: str, roles: list[str]) -> None:
        with self.st.Session.begin() as s:
            self._row(s, email).roles = list(roles)

    def rename(self, email: str, name: str) -> None:
        with self.st.Session.begin() as s:
            self._row(s, email).name = name

    def set_enabled(self, email: str, enabled: bool) -> None:
        with self.st.Session.begin() as s:
            self._row(s, email).enabled = enabled

    def resend_invite(self, email: str) -> None:
        with self.st.Session() as s:
            self._row(s, email)

    def delete(self, email: str) -> None:
        with self.st.Session.begin() as s:
            s.delete(self._row(s, email))


@lru_cache(maxsize=1)
def _cognito() -> CognitoDirectory:
    return CognitoDirectory(os.environ["COGNITO_USER_POOL_ID"],
                            os.environ.get("COGNITO_REGION", os.environ.get("AWS_REGION", "us-east-2")))


def directory(store):
    return LocalDirectory(store) if auth.mode() == "dev" else _cognito()
