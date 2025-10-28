# middleware.py
from django.utils.deprecation import MiddlewareMixin

class NoBackMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
# To use this middleware, add 'cmu_lms.teachers.middleware.NoBackMiddleware' to MIDDLEWARE in settings.py