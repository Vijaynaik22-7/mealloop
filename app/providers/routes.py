from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required

from app.auth.utils import role_required
from app.extensions import db
from app.models import Donation, DonationRequest


# Provider Blueprint
bp = Blueprint(
    'provider',
    __name__,
    url_prefix='/provider'
)

# Donations that are still "in progress" (shown on the dashboard).
# Everything else (collected, expired, cancelled) goes to History.
ACTIVE_STATUSES = ['available', 'requested', 'accepted']


# Get a donation belonging to the logged-in provider
def get_provider_donation(donation_id):

    donation = Donation.query.filter_by(
        id=donation_id,
        provider_id=current_user.id
    ).first_or_404()

    return donation


# Provider Dashboard
@bp.route('/dashboard')
@login_required
@role_required('provider')
def dashboard():

    donations = Donation.query.filter(
        Donation.provider_id == current_user.id,
        Donation.status.in_(ACTIVE_STATUSES)
    ).order_by(
        Donation.created_at.desc()
    ).all()

    return render_template(
        'providers/dashboard.html',
        user=current_user,
        donations=donations
    )


# Create Donation
@bp.route('/donations/create', methods=['GET', 'POST'])
@login_required
@role_required('provider')
def create_donation():

    if request.method == 'POST':

        food_name = request.form.get('food_name', '').strip()
        quantity = request.form.get('quantity', '').strip()
        unit = request.form.get('unit', '').strip()
        prepared_at = request.form.get('prepared_at', '').strip()
        expiry_time = request.form.get('expiry_time', '').strip()
        pickup_location = request.form.get(
            'pickup_location', ''
        ).strip()

        if not all([
            food_name, quantity, unit,
            prepared_at, expiry_time, pickup_location
        ]):
            flash('Please fill in all fields.', 'danger')
            return redirect(url_for('provider.create_donation'))

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            flash(
                'Quantity must be a positive whole number.',
                'danger'
            )
            return redirect(url_for('provider.create_donation'))

        try:
            prepared_at = datetime.fromisoformat(prepared_at)
            expiry_time = datetime.fromisoformat(expiry_time)
        except ValueError:
            flash('Please enter valid dates and times.', 'danger')
            return redirect(url_for('provider.create_donation'))

        if expiry_time <= datetime.now():
            flash('Expiry time must be in the future.', 'danger')
            return redirect(url_for('provider.create_donation'))

        donation = Donation(
            provider_id=current_user.id,
            food_name=food_name,
            quantity=quantity,
            unit=unit,
            prepared_at=prepared_at,
            expiry_time=expiry_time,
            pickup_location=pickup_location,
            status='available'
        )

        db.session.add(donation)
        db.session.commit()

        flash('Food donation listed successfully!', 'success')

        return redirect(url_for('provider.dashboard'))

    return render_template('providers/create.html')


# Edit Donation
@bp.route('/donations/<int:donation_id>/edit',
          methods=['GET', 'POST'])
@login_required
@role_required('provider')
def edit_donation(donation_id):

    donation = get_provider_donation(donation_id)

    if donation.status != 'available':
        flash(
            'Only available donations can be edited.',
            'danger'
        )
        return redirect(url_for('provider.dashboard'))

    if request.method == 'POST':

        food_name = request.form.get('food_name', '').strip()
        quantity = request.form.get('quantity', '').strip()
        unit = request.form.get('unit', '').strip()
        prepared_at = request.form.get('prepared_at', '').strip()
        expiry_time = request.form.get('expiry_time', '').strip()
        pickup_location = request.form.get(
            'pickup_location', ''
        ).strip()

        if not all([
            food_name, quantity, unit,
            prepared_at, expiry_time, pickup_location
        ]):
            flash('Please fill in all fields.', 'danger')
            return redirect(
                url_for('provider.edit_donation',
                        donation_id=donation.id)
            )

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            flash(
                'Quantity must be a positive whole number.',
                'danger'
            )
            return redirect(
                url_for('provider.edit_donation',
                        donation_id=donation.id)
            )

        try:
            prepared_at = datetime.fromisoformat(prepared_at)
            expiry_time = datetime.fromisoformat(expiry_time)
        except ValueError:
            flash('Please enter valid dates and times.', 'danger')
            return redirect(
                url_for('provider.edit_donation',
                        donation_id=donation.id)
            )

        if expiry_time <= datetime.now():
            flash('Expiry time must be in the future.', 'danger')
            return redirect(
                url_for('provider.edit_donation',
                        donation_id=donation.id)
            )

        donation.food_name = food_name
        donation.quantity = quantity
        donation.unit = unit
        donation.prepared_at = prepared_at
        donation.expiry_time = expiry_time
        donation.pickup_location = pickup_location

        db.session.commit()

        flash('Donation updated successfully!', 'success')

        return redirect(url_for('provider.dashboard'))

    return render_template(
        'providers/edit.html',
        donation=donation
    )


# Delete Donation
@bp.route('/donations/<int:donation_id>/delete',
          methods=['POST'])
@login_required
@role_required('provider')
def delete_donation(donation_id):

    donation = get_provider_donation(donation_id)

    if donation.status != 'available':
        flash(
            'Only available donations can be deleted.',
            'danger'
        )
        return redirect(url_for('provider.dashboard'))

    db.session.delete(donation)
    db.session.commit()

    flash('Donation deleted successfully!', 'success')

    return redirect(url_for('provider.dashboard'))


# Provider Donation History (finished donations only)
@bp.route('/history')
@login_required
@role_required('provider')
def donation_history():

    donations = Donation.query.filter(
        Donation.provider_id == current_user.id,
        Donation.status.notin_(ACTIVE_STATUSES)
    ).order_by(
        Donation.created_at.desc()
    ).all()

    return render_template(
        'providers/history.html',
        donations=donations,
        user=current_user
    )


@bp.route('/donations/<int:donation_id>/requests')
@login_required
@role_required('provider')
def donation_requests(donation_id):
    # Only allow the owner of the donation to view its requests.
    donation = Donation.query.filter_by(
        id=donation_id,
        provider_id=current_user.id
    ).first_or_404()

    requests = DonationRequest.query.filter_by(
        donation_id=donation.id
    ).order_by(DonationRequest.created_at.desc()).all()

    return render_template(
        'providers/requests.html',
        donation=donation,
        requests=requests
    )
