document.querySelector("#news-form").addEventListener("submit", function(e) {
  e.preventDefault();

  let form = e.target;

  let title = form.querySelector("[name='title']").value;
  let summary = form.querySelector("[name='summary']").value;
  let content = form.querySelector("[name='content']").value;
  let publishDate = form.querySelector("[name='publish_date']").value;
  let tag = form.querySelector("[name='tag']").value;
  let fileInput = form.querySelector("[name='featured_image']");
  let supplierId = form.querySelector("[name='supplier_id']").value;


  if (fileInput && fileInput.files.length) {
    let file = fileInput.files[0];
    let formData = new FormData();
    formData.append("file", file);
    formData.append("is_private", 0);

    fetch("/api/method/upload_file", {
      method: "POST",
      body: formData,
      headers: {
        "X-Frappe-CSRF-Token": frappe.csrf_token,
      },
    })
      .then((r) => r.json())
      .then((data) => {
        let imageUrl = data.message ? data.message.file_url : null;
        saveNews(title, summary, content, publishDate, tag, imageUrl, supplierId);
      })
      .catch((err) => {
        console.error(err);
        saveNews(title, summary, content, publishDate, tag, null, supplierId);
      });
  } else {
    saveNews(title, summary, content, publishDate, tag, null, supplierId);
  }
});

function saveNews(title, summary, content, publishDate, tag, imageUrl, supplierId) {
  frappe.call({
    method: "frappe.client.insert",
    args: {
      doc: {
        doctype: "qp_SP_Portal_News", 
        title: title,
        summary: summary,
        content: content,
        publish_date: publishDate,
        tag: tag,
        featured_image: imageUrl,
      },
    },
    callback: function (r) {
      if (!r.exc) {
        frappe.msgprint("Noticia creada con éxito");
        window.location.href = "/news?supplier=" + supplierId;
      } else {
        frappe.msgprint("Error al crear la noticia");
      }
    },
  });
}
