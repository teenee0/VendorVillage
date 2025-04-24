# from django_elasticsearch_dsl import Document, fields
# from django_elasticsearch_dsl.registries import registry
# from .models import Product

# @registry.register_document
# class ProductDocument(Document):
#     class Index:
#         name = 'products'
#         settings = {
#             'number_of_shards': 1,
#             'number_of_replicas': 0
#         }
    
#     # Определите поля для поиска
#     name = fields.TextField(attr='name')
#     description = fields.TextField(attr='description')
#     # Если вам нужны еще поля для поиска, добавьте их здесь
    
#     class Django:
#         model = Product
#         fields = [
#             'id',
#             # другие поля, которые нужно включить в результаты
#         ]
# Добавить elastick search