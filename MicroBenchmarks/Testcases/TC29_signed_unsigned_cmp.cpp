// Category: Integer Errors
// Error: Signed/unsigned comparison issue

#include <iostream>

int main() {
    int signedVal = -1;
    unsigned int unsignedVal = 1;
    
    if (signedVal > unsignedVal) {  // ERROR: -1 becomes large positive when compared
        std::cout << "signedVal is greater" << std::endl;  // This will print!
    } else {
        std::cout << "unsignedVal is greater or equal" << std::endl;
    }
    
    return 0;
}
