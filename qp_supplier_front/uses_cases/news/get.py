import frappe

def get_published_news(limit=10, category=None):

    filters = {
        "publish_date": ["<=", frappe.utils.nowdate()]
    }

    news = frappe.get_all(
        "qp_SP_Portal_News",
        filters=filters,
        fields=[
            "name",          
            "title",       
            "summary",      
            "publish_date",  
            "featured_image",       
            "tag"    
        ],
        order_by="publish_date desc",
        limit=limit
    )

    return news

def get_article(article_name):

    article = frappe.get_doc("qp_SP_Portal_News", article_name)

    return article