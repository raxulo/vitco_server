const errors = {

    400: "Bad Request",

    401: "Unauthorized",

    403: "Forbidden",

    404: "Not Found",

    409: "Conflict",

    422: "Validation Error",

    500: "Internal Server Error",

};

function showToast(message, isError = false) {
    const toast = document.getElementById('toast');
    const icon = document.getElementById('toast-icon');
    document.getElementById('toast-message').innerText = message;

    toast.className = 'toast show';
    if (isError) {
        toast.classList.add('error');
        icon.className = 'fa-solid fa-circle-exclamation';
    } else {
        toast.classList.add('success');
        icon.className = 'fa-solid fa-circle-check';
    }

    setTimeout(() => {
        toast.className = 'toast';
    }, 3500);
}

document.body.addEventListener("htmx:configRequest", function (event) {

        // const token = getCookie("access_token");

        // if (token) {
        //     event.detail.headers["Authorization"] = token;
        //     event.detail.credentials = "same-origin";
        // }

    });

document.body.addEventListener("htmx:afterSwap", () => {

    console.log("HTMX Updated");

});

document.body.addEventListener("htmx:beforeRequest", () => {

    document.body.classList.add("loading");

});

document.body.addEventListener("htmx:afterRequest", () => {

    document.body.classList.remove("loading");

});

document.body.addEventListener("notification", (e) => {
    showToast(e.detail.message, e.detail.type === "error");
    // Swal.fire({
    //     icon: e.detail.type,
    //     title: e.detail.title,
    //     text: e.detail.message,
    //     timer: 2000,
    //     showConfirmButton: false,
    // });
});

document.body.addEventListener("redirect", (e) => {
    setTimeout(() => {
        window.location.href = e.detail.url;
    }, e.detail.delay ?? 2000);

});

document.body.addEventListener("htmx:confirm", (e) => {

    if (!e.detail.question) return;

    e.preventDefault();

    Swal.fire({
        title: "Confirmation",
        text: e.detail.question,
        icon: "warning",
        showCancelButton: true,
    }).then((r) => {
        if (r.isConfirmed) {
            e.detail.issueRequest(true);
        }
    });

});

document.body.addEventListener("close-modal", () => {

    document
        .querySelector(".modal.show")
        ?.dispatchEvent(new Event("close"));

});

document.body.addEventListener("form-reset", (e) => {

    document
        .querySelector(e.detail.target)
        ?.reset();

});

document.body.addEventListener("htmx:responseError", (e) => {

    const xhr = e.detail.xhr;
    console.log(xhr);

    let message = errors[xhr.status] ?? "Unexpected Error";

    try {

        const json = JSON.parse(xhr.responseText);

        message = json.error.message??message;

        Swal.fire({

        icon: "error",

        title: "Error",

        text: message,

    });

    }

    catch {}

    

});