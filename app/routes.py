from flask import render_template, request, redirect, url_for, flash, jsonify
from app import app, db
from app.models import User, Campaign, AdRequest, Influencer, Sponsor
from flask_login import login_required as flask_login_required, current_user, login_user, LoginManager, logout_user
from functools import wraps
from datetime import datetime,date
from sqlalchemy import func,case
# Custom login_required decorator to avoid conflict
def custom_login_required(usertype=None):
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('index'))
            if usertype and current_user.role != usertype:
                return redirect(url_for('unauthorized'))  # or raise 403 Forbidden
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

def create_tables():
    with app.app_context():
        db.create_all()
create_tables()

def rows_to_dict(rows):
    return [dict(row) for row in rows]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role=request.form['role']
        username = request.form['username']
        password = request.form['password']
        if role=="None" or not username or not password:
            return render_template('login.html',message="Please enter all details ..")
        user = User.query.filter_by(username=username,role=role).first()
        if not user:
            return render_template('login.html',message="User does not exist !")
        if user and user.password == password:
            login_user(user)
            if role=='Sponsor':
                return redirect(url_for('sponsor_dashboard'))
            if role=='Influencer':
                return redirect(url_for('influencer_dashboard'))
            if role=='Admin':
                return redirect(url_for('admin_dashboard'))
        else:
            return render_template('login.html',message="Incorrect Username or Password !")
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        datejoin= datetime.today().date()
        if User.query.filter_by(username=username).all() or User.query.filter_by(email=email).all():
            return render_template('signup.html',message="Username/Email already exists")
        if role == 'Influencer':
            name = request.form['name']
            category = request.form['category']
            niche = request.form['niche']
            reach = request.form['reach']

            user = User(username=username, email=email, password=password, role=role,joining_date=datejoin)
            db.session.add(user)
            db.session.commit()

            influencer = Influencer(user_id=user.id, name=name, category=category, niche=niche, reach=reach)
            db.session.add(influencer)
            db.session.commit()

        elif role == 'Sponsor':
            company_name = request.form['company_name']
            industry = request.form['industry']
            budget = request.form['budget']

            user = User(username=username, email=email, password=password, role=role,joining_date=datejoin)
            db.session.add(user)
            db.session.commit()

            sponsor = Sponsor(user_id=user.id, company_name=company_name, industry=industry, budget=budget)
            db.session.add(sponsor)
            db.session.commit()

        elif role == 'Admin':
            user = User(username=username, email=email, password=password, role=role,joining_date=datejoin)
            db.session.add(user)
            db.session.commit()

        login_user(user)

        flash('Sign up successful!', 'success')
        return redirect(url_for('index'))

    return render_template('signup.html')


@app.route('/sponsor/dashboard')
@custom_login_required(usertype='Sponsor')
def sponsor_dashboard():
    if current_user.role != 'Sponsor':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    sponsor = Sponsor.query.filter_by(user_id=current_user.id).first()
    campaigns = Campaign.query.filter_by(sponsor_id=current_user.id).all()
    ad_requests = db.session.query(AdRequest).join(Campaign).filter(Campaign.sponsor_id == current_user.id).all()
    ongoing_negotiations = [ad for ad in ad_requests if ad.status == 'Negotiated']

    return render_template('sponsor_dashboard.html', sponsor=sponsor, campaigns=campaigns, ad_requests=ad_requests, ongoing_negotiations=ongoing_negotiations)

@app.route('/admin/dashboard')
@custom_login_required(usertype='Admin')
def admin_dashboard():
    active_users = User.query.count()
    total_campaigns = Campaign.query.count()
    public_campaigns = Campaign.query.filter_by(visibility='public').count()
    private_campaigns = Campaign.query.filter_by(visibility='private').count()
    ad_requests = AdRequest.query.count()
    pending_ad_requests = AdRequest.query.filter_by(status='Pending').count()
    accepted_ad_requests = AdRequest.query.filter_by(status='Accepted').count()
    rejected_ad_requests = AdRequest.query.filter_by(status='Rejected').count()
    negotiated_ad_requests = AdRequest.query.filter_by(status='Negotiated').count()
    flagged_sponsors = Sponsor.query.filter_by(flag=True).count()
    flagged_influencers = Influencer.query.filter_by(flag=True).count()

    return render_template(
        'admin_dashboard.html',
        active_users=active_users,
        total_campaigns=total_campaigns,
        public_campaigns=public_campaigns,
        private_campaigns=private_campaigns,
        ad_requests=ad_requests,
        pending_ad_requests=pending_ad_requests,
        accepted_ad_requests=accepted_ad_requests,
        rejected_ad_requests=rejected_ad_requests,
        negotiated_ad_requests=negotiated_ad_requests,
        flagged_sponsors=flagged_sponsors,
        flagged_influencers=flagged_influencers
    )

@app.route('/admin/search', methods=['GET', 'POST'])
@custom_login_required(usertype='Admin')
def admin_search():
    sponsors = db.session.query(Sponsor)
    influencers = db.session.query(Influencer)

    if request.method == 'POST':
        search_query = request.form.get('search_query', '')
        search_type = request.form.get('search_type', 'all')
        company_name = request.form.get('company_name', '')
        name = request.form.get('name', '')
        is_flagged = request.form.get('is_flagged', '')

        # Search Sponsors
        if search_type in ['sponsor', 'all']:
            query = db.session.query(Sponsor).join(User).filter(Sponsor.user_id == User.id)
            if search_query:
                query = query.filter(User.username.like(f'%{search_query}%'))
            if company_name:
                query = query.filter(Sponsor.company_name.like(f'%{company_name}%'))
            if is_flagged:
                is_flagged = is_flagged.lower() == 'true'
                query = query.filter(Sponsor.is_flagged == is_flagged)
            sponsors = query.all()

        # Search Influencers
        if search_type in ['influencer', 'all']:
            query = db.session.query(Influencer).join(User).filter(Influencer.user_id == User.id)
            if search_query:
                query = query.filter(User.username.like(f'%{search_query}%'))
            if name:
                query = query.filter(Influencer.name.like(f'%{name}%'))
            if is_flagged:
                is_flagged = is_flagged.lower() == 'true'
                query = query.filter(Influencer.is_flagged == is_flagged)
            influencers = query.all()

    return render_template('admin_search.html', sponsors=sponsors, influencers=influencers)

@app.route('/admin/flag/<int:user_id>', methods=['POST'])
@custom_login_required(usertype='Admin')
def flag_user(user_id):
    user = User.query.get_or_404(user_id)
    user.flag = True
    db.session.commit()

    if user.role == 'Sponsor':
        sponsor = Sponsor.query.filter_by(user_id=user.id).first()
        sponsor.flag = True
    elif user.role == 'Influencer':
        influencer = Influencer.query.filter_by(user_id=user.id).first()
        influencer.flag = True

    db.session.commit()
    flash('User flagged successfully', 'success')
    return redirect(url_for('admin_search'))

@app.route('/admin/unflag/<int:user_id>', methods=['POST'])
@custom_login_required(usertype='Admin')
def unflag_user(user_id):
    user = User.query.get_or_404(user_id)
    user.flag = False
    db.session.commit()

    if user.role == 'Sponsor':
        sponsor = Sponsor.query.filter_by(user_id=user.id).first()
        sponsor.flag = False
    elif user.role == 'Influencer':
        influencer = Influencer.query.filter_by(user_id=user.id).first()
        influencer.flag = False

    db.session.commit()
    flash('User unflagged successfully', 'success')
    return redirect(url_for('admin_search'))

@app.route('/view_sponsor/<int:user_id>', methods=['GET'])
@custom_login_required(usertype='Admin')
def view_sponsor(user_id):
    sponsor = Sponsor.query.filter_by(user_id=user_id).first_or_404()
    user=User.query.filter_by(id=sponsor.user_id).first_or_404()
    return render_template('view_sponsor.html', sponsor=sponsor,current_user=user)

@app.route('/delete_sponsor/<int:user_id>', methods=['POST'])
@custom_login_required(usertype='Admin')
def delete_sponsor(user_id):
    sponsor = Sponsor.query.filter_by(user_id=user_id).first_or_404()
    db.session.delete(sponsor)
    db.session.commit()
    flash('Sponsor deleted successfully!')
    return redirect(url_for('admin_search'))

@app.route('/view_influencer/<int:user_id>', methods=['GET'])
@custom_login_required(usertype='Admin')
def view_influencer(user_id):
    influencer = Influencer.query.filter_by(user_id=user_id).first_or_404()
    user=User.query.filter_by(id=influencer.user_id).first_or_404()
    return render_template('view_influencer.html', influencer=influencer,current_user=user)

@app.route('/delete_influencer/<int:user_id>', methods=['POST'])
@custom_login_required(usertype='Admin')
def delete_influencer(user_id):
    influencer = Influencer.query.filter_by(user_id=user_id).first_or_404()
    db.session.delete(influencer)
    db.session.commit()
    flash('Influencer deleted successfully!')
    return redirect(url_for('admin_search'))

@app.route('/sponsor/profile/update', methods=['GET', 'POST'])
@custom_login_required(usertype='Sponsor')
def update_sponsor_profile():
    sponsor = Sponsor.query.filter_by(user_id=current_user.id).first()

    if request.method == 'POST':
        sponsor.company_name = request.form['company_name']
        sponsor.industry = request.form['industry']
        sponsor.budget = request.form['budget']

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('sponsor_dashboard'))

    return render_template('update_sponsor_profile.html', sponsor=sponsor)

@app.route('/sponsor/profile/delete', methods=['POST'])
@custom_login_required(usertype='Sponsor')
def delete_sponsor_profile():
    sponsor = current_user
    user = current_user

    db.session.delete(sponsor)
    db.session.delete(user)
    db.session.commit()

    logout_user()
    flash('Account deleted successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/sponsor/ad_requests/new', methods=['GET', 'POST'])
@custom_login_required('Sponsor')
def new_ad_request():
    if request.method == 'POST':
        datejoin= datejoin = datetime.today().date()
        campaign_id = request.form['campaign_id']
        influencer_id = request.form['influencer_id']
        requirements = request.form['requirements']
        payment_amount = request.form['payment_amount']

        ad_request = AdRequest(
            campaign_id=campaign_id,
            influencer_id=influencer_id,
            requirements=requirements,
            payment_amount=payment_amount,
            status='Pending',issue_date=datejoin
        )

        db.session.add(ad_request)
        db.session.commit()
        flash('Ad Request created successfully!', 'success')
        return redirect(url_for('sponsor_ad_requests'))

    campaigns = Campaign.query.filter_by(sponsor_id=current_user.id).all()
    influencers = Influencer.query.all()
    return render_template('new_ad_request.html', campaigns=campaigns, influencers=influencers)

@app.route('/sponsor/ad_requests')
@custom_login_required('Sponsor')
def sponsor_ad_requests():
    ad_requests = db.session.query(AdRequest).join(Campaign).filter(Campaign.sponsor_id == current_user.id).all()
    return render_template('sponsor_ad_requests.html', ad_requests=ad_requests)

@app.route('/sponsor/ad_requests/<int:ad_request_id>/edit', methods=['GET', 'POST'])
@custom_login_required('Sponsor')
def edit_ad_request(ad_request_id):
    ad_request = AdRequest.query.get_or_404(ad_request_id)

    if request.method == 'POST':
        datejoin= datetime.today().date()
        ad_request.campaign_id = request.form['campaign_id']
        ad_request.influencer_id = request.form['influencer_id']
        ad_request.requirements = request.form['requirements']
        ad_request.payment_amount = request.form['payment_amount']
        ad_request.status = request.form['status']
        ad_request.issue_date=datejoin
        db.session.commit()
        flash('Ad Request updated successfully!', 'success')
        return redirect(url_for('sponsor_ad_requests'))

    campaigns = Campaign.query.filter_by(sponsor_id=current_user.id).all()
    influencers = Influencer.query.all()
    return render_template('edit_ad_request.html', ad_request=ad_request, campaigns=campaigns, influencers=influencers)

@app.route('/ad_requests/<int:ad_request_id>')
def view_ad_request(ad_request_id):
    # Your view function implementation here
    ad_request = AdRequest.query.get_or_404(ad_request_id)
    return render_template('view_ad_request.html', ad_request=ad_request)

@app.route('/sponsor/ad_requests/<int:ad_request_id>/delete', methods=['POST'])
@custom_login_required('Sponsor')
def delete_ad_request(ad_request_id):
    ad_request = AdRequest.query.get_or_404(ad_request_id)
    db.session.delete(ad_request)
    db.session.commit()
    flash('Ad Request deleted successfully!', 'success')
    return redirect(url_for('sponsor_ad_requests'))

@app.route('/influencer/profile/update', methods=['GET', 'POST'])
@custom_login_required(usertype='Influencer')
def update_influencer_profile():
    # Retrieve the Influencer object associated with the current user
    influencer = Influencer.query.filter_by(user_id=current_user.id).first()

    if request.method == 'POST':
        # Update influencer fields with the form data
        influencer.name = request.form['name']
        influencer.category = request.form['category']
        influencer.niche = request.form['niche']
        influencer.reach = request.form['reach']

        # Commit changes to the database
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('influencer_dashboard'))

    return render_template('update_influencer_profile.html', influencer=influencer)

@app.route('/influencer/profile/delete', methods=['POST'])
@custom_login_required(usertype='Influencer')
def delete_influencer_profile():
    influencer = current_user
    user = current_user

    db.session.delete(influencer)
    db.session.delete(user)
    db.session.commit()

    logout_user()
    flash('Account deleted successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/influencer/ad_requests')
@custom_login_required('Influencer')
def influencer_ad_requests():
    inf=Influencer.query.filter_by(user_id=current_user.id).first()
    ad_requests = AdRequest.query.filter_by(influencer_id=inf.id).all()
    print(ad_requests)
    return render_template('influencer_ad_requests.html', ad_requests=ad_requests)

@app.route('/influencer/ad_requests/<int:ad_request_id>/respond', methods=['GET', 'POST'])
@custom_login_required('Influencer')
def respond_ad_request(ad_request_id):
    ad_request = AdRequest.query.get_or_404(ad_request_id)

    if request.method == 'POST':
        ad_request.status = request.form['status']
        ad_request.payment_amount = request.form['payment_amount']
        db.session.commit()
        flash('Ad Request updated successfully!', 'success')
        return redirect(url_for('influencer_ad_requests'))

    return render_template('respond_ad_request.html', ad_request=ad_request)

@app.route('/sponsor/influencer_search', methods=['GET'])
@custom_login_required(usertype='Sponsor')
def sponsor_influencer_search():
    query = request.args.get('query', '')
    niche = request.args.get('niche', '')
    min_reach = request.args.get('min_reach', '')
    
    filters = []
    if query:
        filters.append(Influencer.name.ilike(f'%{query}%'))
    if niche:
        filters.append(Influencer.niche.ilike(f'%{niche}%'))
    if min_reach:
        filters.append(Influencer.reach >= int(min_reach))

    influencers = Influencer.query.filter(*filters).all()
    return render_template('sponsor_influencer_search.html', influencers=influencers, query=query, niche=niche, min_reach=min_reach)

@app.route('/influencer/campaign_search', methods=['GET'])
@custom_login_required(usertype='Influencer')
def influencer_campaign_search():
    query = request.args.get('query', '')
    min_budget = request.args.get('min_budget', '')

    filters = []
    if query:
        filters.append(Campaign.name.ilike(f'%{query}%'))
    if min_budget:
        filters.append(Campaign.budget >= int(min_budget))

    campaigns = Campaign.query.filter(*filters).all()
    return render_template('influencer_campaign_search.html', campaigns=campaigns, query=query, min_budget=min_budget)

@app.route('/sponsor/campaigns/new', methods=['GET', 'POST'])
@custom_login_required(usertype='Sponsor')
def new_campaign():
    if request.method == 'POST':
        datejoin = datetime.today().date()
        name = request.form['name']
        description = request.form['description']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        budget = request.form['budget']
        visibility = request.form['visibility']
        goals = request.form['goals']
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        campaign = Campaign(
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            budget=budget,
            visibility=visibility,
            goals=goals,
            sponsor_id=current_user.id,registered_date=datejoin
        )

        db.session.add(campaign)
        db.session.commit()
        flash('Campaign created successfully!', 'success')
        return redirect(url_for('sponsor_campaigns'))

    return render_template('new_campaign.html')

@app.route('/sponsor/campaigns/<int:campaign_id>/edit', methods=['GET', 'POST'])
@custom_login_required(usertype='Sponsor')
def edit_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)

    if request.method == 'POST':
        campaign.name = request.form['name']
        campaign.description = request.form['description']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        campaign.budget = request.form['budget']
        campaign.visibility = request.form['visibility']
        campaign.goals = request.form['goals']
        campaign.start_date  = datetime.strptime(start_date, '%Y-%m-%d').date()
        campaign.end_date  = datetime.strptime(end_date, '%Y-%m-%d').date()
        db.session.commit()
        flash('Campaign updated successfully!', 'success')
        return redirect(url_for('sponsor_campaigns'))

    return render_template('edit_campaign.html', campaign=campaign)

@app.route('/sponsor/campaigns/<int:campaign_id>/delete', methods=['POST'])
@custom_login_required(usertype='Sponsor')
def delete_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
     # Retrieve all ad requests associated with this campaign
    ad_requests = AdRequest.query.filter_by(campaign_id=campaign.id).all()
    
    # Delete each associated ad request
    for ad_request in ad_requests:
        db.session.delete(ad_request)
    db.session.delete(campaign)
    db.session.commit()
    flash('Campaign deleted successfully!', 'success')
    return redirect(url_for('sponsor_campaigns'))

@app.route('/sponsor/campaigns/<int:campaign_id>', methods=['GET'])
@custom_login_required(usertype='Sponsor')
def view_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    return render_template('view_campaign.html', campaign=campaign)

@app.route('/sponsor/campaigns')
@custom_login_required(usertype='Sponsor')
def sponsor_campaigns():
    # Get the current user's sponsor ID
    sponsor_id = current_user.id
    
    # Query for campaigns created by this sponsor
    campaigns = Campaign.query.filter_by(sponsor_id=sponsor_id).all()
    
    return render_template('sponsor_campaigns.html', campaigns=campaigns)

@app.route('/influencer/dashboard')
@custom_login_required(usertype='Influencer')
def influencer_dashboard():
    if current_user.role != 'Influencer':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))

    influencer = Influencer.query.filter_by(user_id=current_user.id).first()
    ad_requests = AdRequest.query.filter_by(influencer_id=influencer.id).all()
    accepted_campaigns = [ad for ad in ad_requests if ad.status == 'Accepted']
    proposed_negotiations = [ad for ad in ad_requests if ad.status == 'Negotiated']

    print("Influencer:", influencer)
    print("Ad Requests:", ad_requests)
    print("Accepted Campaigns:", accepted_campaigns)
    print("Proposed Negotiations:", proposed_negotiations)

    return render_template('influencer_dashboard.html', influencer=influencer, ad_requests=ad_requests, accepted_campaigns=accepted_campaigns, proposed_negotiations=proposed_negotiations)

@app.route('/admin/stats')
def admin_stats():
    # User Growth Data
    user_growth = {}
    users = User.query.all()

    for user in users:
        month_year = user.joining_date.strftime('%Y-%m')
        if month_year in user_growth:
            user_growth[month_year] += 1
        else:
            user_growth[month_year] = 1

    # Sorting the user growth data by date
    user_growth = dict(sorted(user_growth.items()))

    # Converting dict_keys and dict_values to lists
    user_growth_labels = list(user_growth.keys())
    user_growth_data = list(user_growth.values())

    # Ad Requests Data
    ad_request_status = {
        'Pending': 0,
        'Accepted': 0,
        'Rejected': 0,
        'Negotiated':0
    }
    ad_requests = AdRequest.query.all()

    for ad_request in ad_requests:
        ad_request_status[ad_request.status] += 1

    # Converting dict_keys and dict_values to lists
    ad_request_labels = list(ad_request_status.keys())
    ad_request_data = list(ad_request_status.values())

    return render_template('admin_stats.html', 
                           user_growth_labels=user_growth_labels,
                           user_growth_data=user_growth_data,
                           ad_request_labels=ad_request_labels,
                           ad_request_data=ad_request_data)

@app.route('/sponsor/stats')
@custom_login_required(usertype="Sponsor")
def sponsor_stats():
    campaigns = Campaign.query.filter_by(sponsor_id=current_user.id).all()
    campaign_names = [campaign.name for campaign in campaigns]

    campaign_performance = {campaign.name: [10, 20, 30] for campaign in campaigns}

    sponsor=Sponsor.query.filter_by(user_id=current_user.id).first()
    ad_request_status = {}
    for campaign in campaigns:
        ad_requests = AdRequest.query.filter_by(campaign_id=campaign.id).all()
        statuses = [req.status for req in ad_requests]
        ad_request_status[campaign.name] = {
            'Pending': statuses.count('Pending'),
            'Accepted': statuses.count('Accepted'),
            'Rejected': statuses.count('Rejected'),
            'Negotiated':statuses.count('Negotiated')
        }

    budget_allocation = {campaign.name: campaign.budget for campaign in campaigns}

    return render_template('sponsor_stats.html', 
                           campaign_names=campaign_names, 
                           campaign_performance=campaign_performance,
                           ad_request_status=ad_request_status,
                           budget_allocation={
                               'keys': list(budget_allocation.keys()),  # Access keys method correctly
                               'values': list(budget_allocation.values())  # Access values method correctly
                           },sponsor=sponsor)

@app.route('/influencer/stats')
@custom_login_required(usertype='Influencer')
def influencer_stats():
    # Ensure the influencer exists
    influencer = Influencer.query.filter_by(user_id=current_user.id).first_or_404()

    # Query to get the total payment by campaign for the given influencer
    top_campaigns = db.session.query(
        Campaign.id,
        Campaign.name,
        db.func.sum(AdRequest.payment_amount).label('total_payment')
    ).join(AdRequest, Campaign.id == AdRequest.campaign_id
    ).filter(AdRequest.influencer_id == influencer.id
    ).group_by(Campaign.id
    ).order_by(db.func.sum(AdRequest.payment_amount).desc()
    ).all()

    # Query to get ad request status distribution
    status_distribution = db.session.query(
        AdRequest.status,
        db.func.count(AdRequest.id).label('count')
    ).filter(AdRequest.influencer_id == influencer.id
    ).group_by(AdRequest.status
    ).all()

    # Prepare data for the charts
    top_campaigns_data = {
        'names': [campaign.name for campaign in top_campaigns],
        'payments': [campaign.total_payment for campaign in top_campaigns]
    }

    status_distribution_data = {
        'statuses': [status[0] for status in status_distribution],
        'counts': [status[1] for status in status_distribution]
    }

    return render_template(
        'influencer_stats.html',
        top_campaigns=top_campaigns_data,
        status_distribution=status_distribution_data,
        influencer=influencer
    )


@app.route('/unauthorized')
def unauthorized():
    return render_template('unauthorized.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))
