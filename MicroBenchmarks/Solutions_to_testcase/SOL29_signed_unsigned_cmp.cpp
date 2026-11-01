// Category: Integer Errors (Success Case)
// Expected Result: Cast signed to unsigned or vice-versa correctly for comparison

#include <iostream>

int main() {
    int signedVal = -1;
    unsigned int unsignedVal = 1;
    
    // SUCCESS: Cast unsigned to int for correct comparison, OR ensure both are same type
    if (signedVal > (int)unsignedVal) {
        std::cout << "signedVal is greater" << std::endl;
    } else {
        std::cout << "unsignedVal is greater or equal" << std::endl;  // This will now print correctly
    }
    
    return 0;
}
