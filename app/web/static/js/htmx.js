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

// Errors / warnings need the user's attention: a popup dialog they must close.
// Success / info stay a small toast.
function showErrorPopup(message, title = "Error", icon = "error") {
    if (window.Swal) {
        Swal.fire({
            icon: icon,
            title: title,
            text: message,
            confirmButtonText: "OK",
            confirmButtonColor: "#2563eb",
        });
    } else {
        alert(message);
    }
}

// For forms that submit with fetch(): read the server's error message whether it came
// as JSON ({error: {message}} / {detail}) or as an HX-Trigger "notification" header.
async function responseErrorMessage(res, fallback = "Something went wrong. Please try again.") {
    const trigger = res.headers.get("HX-Trigger");
    if (trigger) {
        try {
            const message = JSON.parse(trigger)?.notification?.message;
            if (message) return message;
        } catch { /* not JSON */ }
    }
    try {
        const json = await res.json();
        const detail = Array.isArray(json?.detail) ? json.detail[0]?.msg : json?.detail;
        return json?.error?.message || detail || fallback;
    } catch {
        return errors[res.status] ?? fallback;
    }
}
window.responseErrorMessage = responseErrorMessage;
window.showErrorPopup = showErrorPopup;

document.body.addEventListener("notification", (e) => {
    const type = e.detail.type;
    if (type === "error" || type === "warning") {
        showErrorPopup(e.detail.message, e.detail.title || (type === "error" ? "Error" : "Warning"), type);
        return;
    }
    showToast(e.detail.message, false);
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

    // The server already sent an HX-Trigger notification -> the listener above shows it
    const trigger = xhr.getResponseHeader("HX-Trigger") || "";
    if (trigger.includes("notification")) return;

    let message = errors[xhr.status] ?? "Unexpected Error";
    try {
        const json = JSON.parse(xhr.responseText);
        message = json?.error?.message ?? json?.detail ?? message;
    } catch {
        // Not JSON (e.g. an HTML error page): keep the status text
    }

    showErrorPopup(message, xhr.status === 422 ? "Please check the form" : "Error");

});

// Network failure (server down / no internet)
document.body.addEventListener("htmx:sendError", () => {
    showErrorPopup("Could not reach the server. Please check your connection and try again.");
});