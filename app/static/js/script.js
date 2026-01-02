// Reset the modal when it is closed
$('#modal-htmx').on('hidden.bs.modal', function () {
        $(this).find('form')[0].reset(); // Reset the form fields
        $(this).find('textarea').remove(); // Clear text areas
});

//var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
//var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
//  return new bootstrap.Tooltip(tooltipTriggerEl)
//});

var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
var tooltipList = tooltipTriggerList.map(function (el) {
  return new bootstrap.Tooltip(el, { trigger: 'hover focus click' });
});

var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'))
var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
  return new bootstrap.Popover(popoverTriggerEl)
});

function requestPermission(){
// Check if notifications are supported
if(typeof(Notification) == "undefined"){
  console.error("Notification not supported");
  return;
};
// We request the permission, which opens a dialog box asking
// for notifications.
var promise = Notification.requestPermission();
// The function returns a promise (which tells in the future the result
// of the notification
promise.then((permission) => {
  // promise.then is only called when the user has clicked 'Allow'
  // or 'Block'
  if(permission !="granted"){
      // If permission is not granted, error
      console.error("Notification permission denied!");
      return;
  };
  // If permission is granted, log that to the console.
  console.log("Permission granted");
})
};

