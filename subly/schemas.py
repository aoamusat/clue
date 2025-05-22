"""
Schema definitions for user authentication.

This module contains Marshmallow schemas for validating API requests
"""

from marshmallow import Schema, fields, validate


class LoginSchema(Schema):
    """Schema for validating login requests.

    Fields:
        username (str): Username between 3-50 characters
        password (str): Password with minimum length of 8 characters
    """

    username = fields.Str(
        required=True,
        validate=validate.Length(min=3, max=50),
    )
    password = fields.Str(
        required=True, load_only=True, validate=validate.Length(min=8)
    )


class RegisterSchema(Schema):
    """Schema for validating user registration requests.

    Fields:
        username (str): Username between 3-50 characters
        email (str): Valid email address
        password (str): Password with minimum length of 8 characters
    """

    username = fields.Str(required=True, validate=validate.Length(min=3, max=50))
    email = fields.Email(required=True)
    password = fields.Str(
        required=True, load_only=True, validate=validate.Length(min=8)
    )


class SubscriptionPlanSchema(Schema):
    """Schema for validating subscription plan requests."""

    duration = fields.Int(required=True)  # Duration in months
    plan_id = fields.Int(required=True)
