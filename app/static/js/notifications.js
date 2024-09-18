function requestPermission(){
    // Check if notifications are supported
    if(typeof(Notification) == "undefined"){
        console.error("Notification not supported");
        return;
    }
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
            console.error("Notification permission denied!")
            return;
        }
        // If permission is granted, log that to the console.
        console.log("Permission granted")
    })
}

